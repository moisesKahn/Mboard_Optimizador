# optimizer_views.py - Motor de optimización simplificado y robusto
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
import json
import uuid
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from django.templatetags.static import static
from django.utils.text import slugify
from django.contrib.staticfiles import finders
from core.models import Proyecto, Cliente, Material, Tapacanto, OptimizationRun, AuditLog
from core.auth_utils import get_auth_context
import math

def _normalize_rut(rut: str) -> str:
    """Normaliza un RUT/identificador para comparación: quita puntos, guiones y espacios, y pasa a mayúsculas.
    Evita duplicados por formato (ej. 12.345.678-9 vs 12345678-9).
    """
    if not rut:
        return ''
    try:
        s = str(rut).upper()
        # quitar espacios, puntos y guiones
        for ch in [' ', '.', '-']:
            s = s.replace(ch, '')
        return s
    except Exception:
        return str(rut).strip()

class TipoMaterial:
    TABLERO = 'tablero'

class OptimizationEngine:
    """Motor de optimización simplificado que evita superposiciones"""
    def __init__(self, tablero_ancho, tablero_largo, margen_x, margen_y, desperdicio_sierra):
        self.tablero_ancho_original = tablero_ancho
        self.tablero_largo_original = tablero_largo
        self.tablero_ancho = tablero_ancho - (2 * margen_x)
        self.tablero_largo = tablero_largo - (2 * margen_y)
        self.margen_x = margen_x
        self.margen_y = margen_y
        self.desperdicio_sierra = desperdicio_sierra
        self.tableros = []

    def optimizar_piezas(self, piezas):
        """Algoritmo de optimización principal con timeout y colocación Bottom-Left"""
        import time
        tiempo_inicio = time.time()
        timeout_segundos = 30

        # Expandir piezas por cantidad
        piezas_individuales = []
        for pieza in piezas:
            for i in range(pieza.get('cantidad', 1)):
                pi = pieza.copy(); pi['id_unico'] = f"{pieza['nombre']}_{i+1}"; pi['cantidad'] = 1
                piezas_individuales.append(pi)

        # Orden: primero áreas mayores
        def criterio(p):
            area = p['ancho'] * p['largo']
            max_dim = max(p['ancho'], p['largo'])
            return (-area, -max_dim)
        piezas_individuales.sort(key=criterio)

        piezas_no_colocadas = []

        for i, pieza in enumerate(piezas_individuales):
            if time.time() - tiempo_inicio > timeout_segundos:
                piezas_no_colocadas.extend(piezas_individuales[i:])
                break

            colocada = False
            # Probar primero en tableros existentes (más llenos primero)
            tableros_ordenados = sorted(self.tableros, key=lambda t: len(t['piezas']), reverse=True)
            for tablero in tableros_ordenados:
                if self._colocar_pieza_en_tablero(tablero, pieza):
                    colocada = True
                    break
                if time.time() - tiempo_inicio > timeout_segundos:
                    break

            # Crear nuevo tablero si no cupo
            if not colocada and time.time() - tiempo_inicio <= timeout_segundos:
                nuevo = self._crear_nuevo_tablero()
                if self._colocar_pieza_en_tablero(nuevo, pieza):
                    self.tableros.append(nuevo)
                    colocada = True
                else:
                    piezas_no_colocadas.append(pieza)
            elif not colocada:
                piezas_no_colocadas.append(pieza)

        # Generar resultado y ajustar métricas
        resultado = self._generar_resultado()
        resultado['piezas_no_colocadas'] = len(piezas_no_colocadas)
        resultado['tiempo_optimizacion'] = time.time() - tiempo_inicio
        return resultado

    def _colocar_pieza_en_tablero(self, tablero, pieza):
        # Validar si cabe o intentar rotación si veta libre
        if (pieza['ancho'] > self.tablero_ancho or pieza['largo'] > self.tablero_largo):
            if (pieza.get('veta_libre', False) and pieza['largo'] <= self.tablero_ancho and pieza['ancho'] <= self.tablero_largo):
                orientaciones = [(pieza['largo'], pieza['ancho'], True)]
            else:
                return False
        else:
            orientaciones = [(pieza['ancho'], pieza['largo'], False)]
            if (pieza.get('veta_libre', False) and pieza['largo'] <= self.tablero_ancho and pieza['ancho'] <= self.tablero_largo):
                orientaciones.append((pieza['largo'], pieza['ancho'], True))

        for ancho, largo, rotada in orientaciones:
            pos = self._encontrar_posicion_libre(tablero, ancho, largo)
            if pos:
                x, y = pos['x'], pos['y']
                if (x + ancho <= self.tablero_ancho and y + largo <= self.tablero_largo):
                    nueva = {
                        'nombre': pieza['nombre'],
                        'id_unico': pieza.get('id_unico', pieza['nombre']),
                        'x': x, 'y': y,
                        'ancho': ancho, 'largo': largo,
                        'rotada': rotada,
                        'tapacantos': pieza.get('tapacantos', {}),
                        'veta_libre': pieza.get('veta_libre', False)
                    }
                    tablero['piezas'].append(nueva)
                    return True
        return False

    def _encontrar_posicion_libre(self, tablero, ancho, largo):
        if ancho > self.tablero_ancho or largo > self.tablero_largo:
            return None
        if not tablero['piezas']:
            return {'x': 0, 'y': 0}

        posiciones = set()
        posiciones.add((0, 0))
        for p in tablero['piezas']:
            x_der = p['x'] + p['ancho'] + self.desperdicio_sierra
            y_sup = p['y'] + p['largo'] + self.desperdicio_sierra
            if x_der + ancho <= self.tablero_ancho:
                if p['y'] + largo <= self.tablero_largo:
                    posiciones.add((x_der, p['y']))
                if y_sup + largo <= self.tablero_largo:
                    posiciones.add((x_der, y_sup))
            if y_sup + largo <= self.tablero_largo:
                if p['x'] + ancho <= self.tablero_ancho:
                    posiciones.add((p['x'], y_sup))
                x_der2 = p['x'] + p['ancho'] + self.desperdicio_sierra
                if x_der2 + ancho <= self.tablero_ancho:
                    posiciones.add((x_der2, y_sup))
            # Alineadas
            if p['x'] + ancho <= self.tablero_ancho and p['y'] + largo <= self.tablero_largo:
                posiciones.add((p['x'], p['y']))

        pos_list = list(posiciones)
        pos_list.sort(key=lambda pos: (pos[1], pos[0]))
        for (x, y) in pos_list:
            if self._posicion_libre(tablero, x, y, ancho, largo):
                return {'x': x, 'y': y}
        # Búsqueda sistemática si no hubo suerte
        # Volver a la lógica anterior: paso fijo de 15 mm
        paso = 15
        for y in range(0, self.tablero_largo - largo + 1, paso):
            for x in range(0, self.tablero_ancho - ancho + 1, paso):
                if self._posicion_libre(tablero, x, y, ancho, largo):
                    return {'x': x, 'y': y}
        return None

    def _posicion_libre(self, tablero, x, y, ancho, largo):
        if (x < 0 or y < 0 or x + ancho > self.tablero_ancho or y + largo > self.tablero_largo):
            return False
        for p in tablero['piezas']:
            nuevo_x1, nuevo_y1 = x, y
            nuevo_x2, nuevo_y2 = x + ancho, y + largo
            exist_x1, exist_y1 = p['x'], p['y']
            exist_x2, exist_y2 = p['x'] + p['ancho'], p['y'] + p['largo']
            margen = self.desperdicio_sierra
            overlap_x = not (nuevo_x2 + margen <= exist_x1 or exist_x2 + margen <= nuevo_x1)
            overlap_y = not (nuevo_y2 + margen <= exist_y1 or exist_y2 + margen <= nuevo_y1)
            if overlap_x and overlap_y:
                return False
        return True

    def _crear_nuevo_tablero(self):
        return {
            'id': len(self.tableros) + 1,
            'ancho': self.tablero_ancho,
            'largo': self.tablero_largo,
            'piezas': [],
            'area_usada': 0
        }

    def _generar_resultado(self):
        total_area_tableros = len(self.tableros) * (self.tablero_ancho * self.tablero_largo)
        area_utilizada = 0
        total_piezas = 0
        for tablero in self.tableros:
            area_tablero = 0
            for pieza in tablero['piezas']:
                area_pieza = pieza['ancho'] * pieza['largo']
                area_utilizada += area_pieza
                area_tablero += area_pieza
                total_piezas += 1
            tablero['area_usada'] = area_tablero
            tablero['area_total'] = self.tablero_ancho * self.tablero_largo
            tablero['area_utilizada'] = area_tablero
            tablero['eficiencia_tablero'] = (area_tablero / (self.tablero_ancho * self.tablero_largo)) * 100
            # Ajustes para visualización (incluir márgenes)
            for pieza in tablero['piezas']:
                pieza['x'] += self.margen_x
                pieza['y'] += self.margen_y
            tablero['ancho'] = self.tablero_ancho_original
            tablero['largo'] = self.tablero_largo_original
            tablero['ancho_trabajo'] = self.tablero_ancho
            tablero['largo_trabajo'] = self.tablero_largo

        eficiencia = (area_utilizada / total_area_tableros * 100) if total_area_tableros > 0 else 0
        return {
            'tableros': self.tableros,
            'total_tableros': len(self.tableros),
            'total_piezas': total_piezas,
            'area_utilizada': area_utilizada / 1000000,
            'eficiencia': round(eficiencia, 1),
            'area_total': total_area_tableros / 1000000,
            'desperdicio_sierra': self.desperdicio_sierra,
            'tablero_ancho_efectivo': self.tablero_ancho,
            'tablero_largo_efectivo': self.tablero_largo,
            'tablero_ancho_original': self.tablero_ancho_original,
            'tablero_largo_original': self.tablero_largo_original,
            'margenes': {
                'margen_x': self.margen_x,
                'margen_y': self.margen_y
            }
        }
def optimizador_home_clasico(request):
    """Versión clásica del optimizador (conservada por compatibilidad)."""
    ctx = get_auth_context(request)
    base = Proyecto.objects.filter(usuario=request.user)
    if not (ctx.get('organization_is_general') or ctx.get('is_support')):
        base = base.filter(organizacion_id=ctx.get('organization_id'))
    proyectos = base.order_by('-fecha_creacion')[:10]
    clientes = Cliente.objects.all()
    tableros = Material.objects.all()
    tapacantos = Tapacanto.objects.all()

    context = {
        'proyectos': proyectos,
        'clientes': clientes,
        'tableros': tableros,
        'tapacantos': tapacantos,
    }
    return render(request, 'optimizador/home.html', context)

# ------------------------------
# Renderizado de PDF desde resultado
# ------------------------------
def _materiales_desde_resultado(resultado):
    if not isinstance(resultado, dict):
        return []
    mats = resultado.get('materiales')
    if isinstance(mats, list) and mats:
        return mats
    # Soportar caso single-material plano
    if resultado.get('tableros'):
        return [resultado]
    return []

def _pdf_from_result(proyecto, resultado):
    """Genera un PDF (bytes) que dibuja cada tablero y sus piezas según el resultado guardado.
    Paridad 1:1 con la vista: coords relativas al área útil con origen arriba-izquierda.
    """
    from io import BytesIO
    buf = BytesIO()

    # Canvas con numeración total de páginas
    class NumberedCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states = []
            self._page_width, self._page_height = landscape(letter)
        def showPage(self):
            # Guarda el estado de la página actual y empieza una nueva
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()
        def save(self):
            # Asegurar que el estado de la página actual también esté incluido
            # (si no se llamó a showPage() tras el último contenido, se perdería la última página).
            try:
                self._saved_page_states.append(dict(self.__dict__))
            except Exception:
                pass
            # Inserta numeración "Página X de Y" centrada abajo
            page_count = len(self._saved_page_states)
            for i, state in enumerate(self._saved_page_states, start=1):
                self.__dict__.update(state)
                self._draw_page_number(i, page_count)
                canvas.Canvas.showPage(self)
            canvas.Canvas.save(self)
        def _draw_page_number(self, page_num, page_count):
            try:
                self.setFont("Helvetica", 9)
                txt = f"Página {page_num} de {page_count}"
                self.drawCentredString(self._page_width/2.0, 18, txt)
            except Exception:
                pass

    # PDF en orientación horizontal (apaisado)
    p = NumberedCanvas(buf, pagesize=landscape(letter))
    width, height = landscape(letter)
    # Título del documento para evitar "Untitled" en el viewer
    try:
        cliente_slug = slugify(proyecto.cliente.nombre) if proyecto.cliente_id else 'cliente'
    except Exception:
        cliente_slug = 'cliente'
    try:
        folio_txt = str(getattr(proyecto, 'public_id', '') or '')
    except Exception:
        folio_txt = ''
    p.setTitle(f"Optimizacion_{folio_txt or proyecto.codigo}_{cliente_slug}")
    # Modo rápido: simplificar hachurado de márgenes para acelerar generación
    FAST_PDF = True

    materiales = _materiales_desde_resultado(resultado)
    if not materiales:
        # Página mínima informativa si no hay resultado
        p.setFont("Helvetica-Bold", 16)
        p.drawString(40, height-70, f"{proyecto.nombre}")
        y = height-110
        p.setFont("Helvetica", 10)
        p.drawString(40, y, f"Cliente: {proyecto.cliente.nombre if proyecto.cliente_id else '-'}"); y -= 16
        p.drawString(40, y, f"Código de proyecto: {proyecto.codigo}"); y -= 16
        p.drawString(40, y, "No hay resultado de optimización guardado.")
        p.showPage(); p.save(); data = buf.getvalue(); buf.close(); return data

    # Página(s) de resumen con logo
    # Cache de logo para mejorar rendimiento
    _logo_reader = None
    try:
        _logo_path = finders.find('images/logo.png') or finders.find('logo.png')
        if _logo_path:
            _logo_reader = ImageReader(_logo_path)
    except Exception:
        _logo_reader = None

    def draw_logo(top_right_x, top_right_y):
        try:
            if _logo_reader:
                p.drawImage(_logo_reader, top_right_x-80, top_right_y-50, width=70, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    def draw_table_header(y, cols):
        # Minimizar cambios de fuente
        p.setFont("Helvetica-Bold", 10)
        x=40
        for label,wc in cols:
            p.drawString(x, y, label)
            x += wc
        p.line(40, y-4, width-40, y-4)

    def draw_table_header_at(x0, y, cols, total_w):
        """Dibuja cabecera de tabla en una X específica y dentro de un ancho total dado.
        cols: lista de (label, width) cuyos anchos deben sumar <= total_w
        """
        p.setFont("Helvetica-Bold", 9)
        x = x0
        for label, wc in cols:
            p.drawString(x, y, label)
            x += wc
        # línea inferior de la cabecera limitada al ancho de la tabla
        p.line(x0, y-3, x0 + total_w, y-3)

    def normalizar_taps(taps: dict):
        """Devuelve tupla ordenada de lados con tapacanto activos.
        Nota: ya no se usa para agrupar en tablas, solo para cálculos auxiliares.
        """
        try:
            lados = tuple(sorted([k for k,v in (taps or {}).items() if v]))
            return lados
        except Exception:
            return tuple()

    def agrupar_piezas_por_material(mat):
        """Agrupa piezas por nombre y dimensiones ignorando rotación y sin dividir por veta/tapacantos.
        - Cuenta total por tipo (min(ancho, largo), max(ancho, largo)).
        - Veta: marca 'Libre' si alguna instancia del nombre/dim tiene veta libre, de lo contrario '-'.
        - Observación: si todas las instancias comparten el mismo número de lados con tapacanto
          (1, 2 o 4) se muestra, en caso contrario 'Mixto' o vacío.
        """
        # Construir lookup de veta libre a partir de 'entrada'
        veta_lookup = {}
        veta_por_nombre = {}
        try:
            for e in (mat.get('entrada') or []):
                nombre_e = e.get('nombre')
                a = int(e.get('ancho',0)); l = int(e.get('largo',0))
                # Para lookup por orientación directa y rotada
                key = (nombre_e, min(a,l), max(a,l))
                is_libre = bool(e.get('veta_libre'))
                veta_lookup[key] = 'Libre' if is_libre else '-'
                # Guardar por nombre para fallback
                if nombre_e not in veta_por_nombre:
                    veta_por_nombre[nombre_e] = is_libre
                else:
                    veta_por_nombre[nombre_e] = veta_por_nombre[nombre_e] or is_libre
        except Exception:
            pass

        grupos = {}
        for t in (mat.get('tableros') or []):
            for pz in (t.get('piezas') or []):
                a = int(pz.get('ancho',0)); l = int(pz.get('largo',0))
                key = (
                    pz.get('nombre'),
                    min(a,l),
                    max(a,l)
                )
                g = grupos.get(key)
                if not g:
                    taps = pz.get('tapacantos') or {}
                    n_lados = len([k for k,v in taps.items() if v])
                    # Veta: preferir por nombre+dimensiones sin importar rotación
                    nombre_p = pz.get('nombre')
                    veta = veta_lookup.get((nombre_p, min(a,l), max(a,l)))
                    if not veta:
                        veta = 'Libre' if veta_por_nombre.get(nombre_p) else '-'
                    g = grupos[key] = {
                        'nombre': pz.get('nombre',''),
                        'ancho': min(a,l),
                        'largo': max(a,l),
                        'veta': veta,
                        'observacion': '',
                        'cantidad': 0,
                        '_lados_set': set([n_lados]),
                    }
                else:
                    # Agregar variación de lados para decidir observación agregada
                    taps2 = pz.get('tapacantos') or {}
                    n_lados2 = len([k for k,v in taps2.items() if v])
                    g.setdefault('_lados_set', set()).add(n_lados2)
                g['cantidad'] += 1
        # Consolidar observación agregada
        for v in grupos.values():
            lados_set = v.pop('_lados_set', set())
            if len(lados_set) == 1:
                n = next(iter(lados_set))
                if n == 4:
                    v['observacion'] = '4 lados'
                elif n == 2:
                    v['observacion'] = '2 lados'
                elif n == 1:
                    v['observacion'] = '1 lado'
                else:
                    v['observacion'] = ''
            elif len(lados_set) > 1:
                v['observacion'] = 'Mixto'
        grouped_list = sorted(grupos.values(), key=lambda r: (r['nombre'], r['ancho'], r['largo']))
        return grouped_list

    # Portada global: información del proyecto + resumen de TODOS los materiales seleccionados
    try:
        materiales = _materiales_desde_resultado(resultado)
    except Exception:
        materiales = _materiales_desde_resultado(resultado)
    if materiales:
        draw_logo(width-40, height-40)
        # Título e ID del proyecto
        p.setFont("Helvetica-Bold", 16)
        p.drawString(40, height-60, f"{proyecto.nombre} - {datetime.now().strftime('%d-%m-%Y')}")
        try:
            folio_txt = str(getattr(proyecto, 'public_id', '') or '') or (resultado.get('folio_proyecto') if isinstance(resultado, dict) else '')
        except Exception:
            folio_txt = ''
        if not folio_txt:
            try:
                # Compatibilidad: si aún no hay public_id, mostrar correlativo-versión
                folio_txt = f"{proyecto.correlativo}-{proyecto.version}"
            except Exception:
                folio_txt = ''
        if folio_txt:
            p.setFont("Helvetica", 10)
            p.drawRightString(width-40, height-60, f"ID del proyecto: {folio_txt}")
        # Datos base (espaciado más compacto)
        y = height-88
        p.setFont("Helvetica", 10)
        cliente_txt = (proyecto.cliente.nombre if getattr(proyecto, 'cliente_id', None) else '-')
        p.drawString(40, y, f"Cliente:  {cliente_txt}"); y -= 12
        p.drawString(40, y, f"Proyecto: {proyecto.nombre} ({proyecto.codigo})"); y -= 14
        # Resumen de materiales seleccionados
        p.setFont("Helvetica-Bold", 12)
        p.drawString(40, y, "Resumen de materiales seleccionados"); y -= 18
        draw_table_header(y, [("Material",200),("Tableros",80),("Piezas",80),("Aprovech.",100)]); y -= 18
        p.setFont("Helvetica", 10)
        for idx_mat_tbl, m in enumerate(materiales, start=1):
            mat_name_base = (m.get('material') or {}).get('nombre') or (m.get('material_nombre') or 'Material')
            mat_name = f"{idx_mat_tbl}. {mat_name_base}"
            tabs = len(m.get('tableros') or [])
            piezas_cnt = sum(len(t.get('piezas',[])) for t in (m.get('tableros') or []))
            eff = m.get('eficiencia') or m.get('eficiencia_promedio') or (resultado.get('eficiencia_promedio') if isinstance(resultado, dict) else 0) or 0
            x = 40
            p.drawString(x, y, str(mat_name)); x += 200
            p.drawString(x, y, str(tabs)); x += 80
            p.drawString(x, y, str(piezas_cnt)); x += 80
            p.drawString(x, y, f"{eff}%");
            y -= 14
            if y < 120:
                p.showPage(); draw_logo(width-40, height-40)
                y = height-90
                p.setFont("Helvetica-Bold", 12)
                p.drawString(40, y, "Resumen de materiales seleccionados (cont.)"); y -= 18
                draw_table_header(y, [("Material",200),("Tableros",80),("Piezas",80),("Aprovech.",100)]); y -= 18
                p.setFont("Helvetica", 10)
        # Resumen de piezas ubicadas (agregado por material+pieza+dimensiones+lados)
        def _taps_key_and_str(taps: dict):
            try:
                lados = []
                if (taps or {}).get('arriba'): lados.append('A')
                if (taps or {}).get('derecha'): lados.append('D')
                if (taps or {}).get('abajo'): lados.append('B')
                if (taps or {}).get('izquierda'): lados.append('I')
                return tuple(lados), (','.join(lados) if lados else '—')
            except Exception:
                return tuple(), '—'

        # Añadir un pequeño espacio extra antes del resumen de piezas
        if y >= 140:
            y -= 10
        # Si queda poco espacio, pasar a la siguiente página antes de iniciar la tabla
        if y < 120:
            p.showPage(); draw_logo(width-40, height-40)
            y = height-90
        p.setFont("Helvetica-Bold", 12)
        p.drawString(40, y, "Resumen de piezas ubicadas"); y -= 18
        piezas_cols = [("Pieza",160),("Cant.",40),("Ancho",50),("Alto",50),("Material",80),("Tapacanto",80),("Lados (A/D/B/I)",70)]
        draw_table_header(y, piezas_cols); y -= 18
        p.setFont("Helvetica", 9)

        agregados = {}
        for idx_mat, mat in enumerate(materiales, start=1):
            tap_code = (mat.get('tapacanto') or {}).get('codigo') or '—'
            for t in (mat.get('tableros') or []):
                for pz in (t.get('piezas') or []):
                    try:
                        nombre = pz.get('nombre', '')
                        a = int(pz.get('ancho', 0)); l = int(pz.get('largo', pz.get('alto', 0)))
                        w, h = (a if a <= l else l), (l if l >= a else a)
                        k_t, s_t = _taps_key_and_str(pz.get('tapacantos') or {})
                        key = (idx_mat, nombre, w, h, k_t, tap_code)
                        if key not in agregados:
                            agregados[key] = {
                                'pieza': nombre,
                                'cant': 0,
                                'ancho': w,
                                'alto': h,
                                'material': f"Material {idx_mat}",
                                'tapacanto': tap_code,
                                'lados': s_t,
                            }
                        agregados[key]['cant'] += 1
                    except Exception:
                        continue

        filas = list(agregados.values())
        filas.sort(key=lambda r: (r['material'], r['pieza'], r['ancho'], r['alto'], r['lados']))
        for row in filas:
            if y < 80:
                p.showPage(); draw_logo(width-40, height-40)
                y = height-90
                p.setFont("Helvetica-Bold", 12)
                p.drawString(40, y, "Resumen de piezas ubicadas (cont.)"); y -= 18
                draw_table_header(y, piezas_cols); y -= 18
                p.setFont("Helvetica", 9)
            x = 40
            p.drawString(x, y, str(row['pieza'])); x += piezas_cols[0][1]
            p.drawString(x, y, str(row['cant'])); x += piezas_cols[1][1]
            p.drawString(x, y, str(row['ancho'])); x += piezas_cols[2][1]
            p.drawString(x, y, str(row['alto'])); x += piezas_cols[3][1]
            p.drawString(x, y, str(row['material'])); x += piezas_cols[4][1]
            p.drawString(x, y, str(row['tapacanto'])); x += piezas_cols[5][1]
            p.drawString(x, y, str(row['lados']))
            y -= 12

        # Añadir espacio antes del detalle por material
        y -= 12
        # Detalle por material (compacto en 3 columnas)
        p.setFont("Helvetica-Bold", 12)
        p.drawString(40, y, "Detalle por material"); y -= 14
        # Config columnas: 3 columnas compactas
        col_count = 3
        col_gap = 14
        col_left_x = 40
        total_w = (width - 80)
        col_width = (total_w - (col_count-1)*col_gap) / float(col_count)
        col_mid_x = col_left_x + col_width + col_gap
        col_right_x = col_mid_x + col_width + col_gap
        line_h = 10
        from reportlab.pdfbase.pdfmetrics import stringWidth

        def wrap_text(txt, font_name, font_size, max_w):
            words = str(txt).split(' ')
            lines = []
            cur = ''
            for w in words:
                cand = (cur + (' ' if cur else '') + w)
                if stringWidth(cand, font_name, font_size) <= max_w:
                    cur = cand
                else:
                    if cur:
                        lines.append(cur)
                    cur = w
            if cur:
                lines.append(cur)
            return lines

        def material_block_lines(idx, mat):
            try:
                kerf = (mat.get('config') or {}).get('kerf', mat.get('desperdicio_sierra', 0))
                mx = (mat.get('margenes') or {}).get('margen_x', (mat.get('config') or {}).get('margen_x', 0))
                my = (mat.get('margenes') or {}).get('margen_y', (mat.get('config') or {}).get('margen_y', 0))
                orig_w = int(mat.get('tablero_ancho_original', (mat.get('material') or {}).get('ancho_original', 0)))
                orig_h = int(mat.get('tablero_largo_original', (mat.get('material') or {}).get('largo_original', 0)))
                util_w = int(mat.get('tablero_ancho_efectivo', max(0, (orig_w - 2*int(mx)))))
                util_h = int(mat.get('tablero_largo_efectivo', max(0, (orig_h - 2*int(my)))))
                tap_info = (mat.get('tapacanto') or {})
                tapc_name = tap_info.get('nombre') or ''
                tapc_code = tap_info.get('codigo') or ''
                tapc = (f"{tapc_name} ({tapc_code})".strip() if (tapc_name or tapc_code) else '—')
                tabs = len(mat.get('tableros') or [])
                pzs = sum(len(t.get('piezas',[])) for t in (mat.get('tableros') or []))
                eff = mat.get('eficiencia') or mat.get('eficiencia_promedio') or (resultado.get('eficiencia_promedio') if isinstance(resultado, dict) else 0) or 0
            except Exception:
                kerf, mx, my, orig_w, orig_h, util_w, util_h, tapc, tabs, pzs, eff = 0,0,0,0,0,0,0,'—',0,0,0
            mat_title = (mat.get('material') or {}).get('nombre') or 'Material'
            header = f"Material {idx}: {mat_title}"
            # Devuelve (texto, bold) para permitir resaltar el tapacanto sin usar **
            details = [
                (f"Kerf: {kerf} mm", False),
                (f"Márgenes: x={mx} y={my}", False),
                (f"Tablero (orig/útil): {orig_w}×{orig_h} / {util_w}×{util_h} mm", False),
                ("Tapacanto:", False),
                (tapc, True),
                (f"Tableros: {tabs}   Piezas: {pzs}", False),
                (f"Aprovechamiento: {eff}%", False),
            ]
            return header, details

        i = 1
        y_row_top = y
        while i <= len(materiales):
            # Preparar bloques para 3 columnas
            left_mat = materiales[i-1]
            mid_mat = materiales[i] if (i) < len(materiales) else None
            right_mat = materiales[i+1] if (i+1) < len(materiales) else None

            left_header, left_details = material_block_lines(i, left_mat)
            mid_header = mid_details = right_header = right_details = None
            if mid_mat is not None:
                mid_header, mid_details = material_block_lines(i+1, mid_mat)
            if right_mat is not None:
                right_header, right_details = material_block_lines(i+2, right_mat)

            # Calcular alturas (compactas)
            def block_height(header, details):
                if not header:
                    return 0
                h = len(wrap_text(header, 'Helvetica-Bold', 9, col_width)) * line_h
                if details:
                    for d, is_bold in details:
                        font = 'Helvetica-Bold' if is_bold else 'Helvetica'
                        h += len(wrap_text(d, font, 8, col_width)) * line_h
                return h

            left_height = block_height(left_header, left_details)
            mid_height = block_height(mid_header, mid_details)
            right_height = block_height(right_header, right_details)
            row_height = max(left_height, mid_height, right_height)

            if y_row_top - row_height < 80:
                # Nueva página para continuar el detalle en columnas
                p.showPage(); draw_logo(width-40, height-40)
                y_row_top = height-90
                p.setFont('Helvetica-Bold', 12)
                p.drawString(40, y_row_top, 'Detalle por material (cont.)'); y_row_top -= 14

            # Dibujar bloque izquierdo
            ycur = y_row_top
            p.setFont('Helvetica-Bold', 9)
            for line in wrap_text(left_header, 'Helvetica-Bold', 9, col_width):
                p.drawString(col_left_x, ycur, line)
                ycur -= line_h
            if left_details:
                for d, is_bold in left_details:
                    font = 'Helvetica-Bold' if is_bold else 'Helvetica'
                    p.setFont(font, 8)
                    for line in wrap_text(d, font, 8, col_width):
                        p.drawString(col_left_x, ycur, line)
                        ycur -= line_h

            # Bloque medio
            if mid_header:
                ycur_m = y_row_top
                p.setFont('Helvetica-Bold', 9)
                for line in wrap_text(mid_header, 'Helvetica-Bold', 9, col_width):
                    p.drawString(col_mid_x, ycur_m, line)
                    ycur_m -= line_h
                if mid_details:
                    for d, is_bold in mid_details:
                        font = 'Helvetica-Bold' if is_bold else 'Helvetica'
                        p.setFont(font, 8)
                        for line in wrap_text(d, font, 8, col_width):
                            p.drawString(col_mid_x, ycur_m, line)
                            ycur_m -= line_h

            # Bloque derecho
            if right_header:
                ycur_r = y_row_top
                p.setFont('Helvetica-Bold', 9)
                for line in wrap_text(right_header, 'Helvetica-Bold', 9, col_width):
                    p.drawString(col_right_x, ycur_r, line)
                    ycur_r -= line_h
                if right_details:
                    for d, is_bold in right_details:
                        font = 'Helvetica-Bold' if is_bold else 'Helvetica'
                        p.setFont(font, 8)
                        for line in wrap_text(d, font, 8, col_width):
                            p.drawString(col_right_x, ycur_r, line)
                            ycur_r -= line_h

            # Avanzar a la siguiente fila
            y_row_top -= row_height + 8
            i += 3
    p.showPage()

    # Un tablero por página, por cada material (páginas horizontales sin tabla inferior)
    for m_idx, mat in enumerate(materiales, start=1):
        # Precalcular totales globales por tipo (nombre + dimensiones normalizadas) en TODO el material
        # para que las etiquetas (i/j) coincidan con el visualizador (no por tablero).
        totales_global_por_tipo = {}
        for t_all in (mat.get('tableros') or []):
            for pz_all in (t_all.get('piezas') or []):
                a_all = int(pz_all.get('ancho', 0)); l_all = int(pz_all.get('largo', 0))
                k_all = (pz_all.get('nombre'), min(a_all, l_all), max(a_all, l_all))
                totales_global_por_tipo[k_all] = totales_global_por_tipo.get(k_all, 0) + 1

        # Contadores de corrida globales por tipo (persisten a través de todos los tableros del material)
        corridas_global_por_tipo = {}
        # Medidas efectivas
        try:
            margen_x = float((mat.get('margenes') or {}).get('margen_x', (mat.get('config') or {}).get('margen_x', 0)))
        except Exception:
            margen_x = 0.0
        try:
            margen_y = float((mat.get('margenes') or {}).get('margen_y', (mat.get('config') or {}).get('margen_y', 0)))
        except Exception:
            margen_y = 0.0

        tableros_mat = (mat.get('tableros') or [])
        total_tabs_mat = len(tableros_mat)
        for t_idx, t in enumerate(tableros_mat, start=1):
            # Preparar layout de página: logo y áreas reservadas (cabecera y tabla inferior)
            draw_logo(width-40, height-40)
            header_reserved = 90  # reservar un poco más para evitar solapes
            bottom_reserved = 20  # sin tabla inferior aquí
            margin_lr = 20
            box_w = width - 2*margin_lr
            box_h = height - (header_reserved + bottom_reserved)

            # Dimensiones del tablero (mm)
            tw = float(t.get('ancho', mat.get('tablero_ancho_original') or 1))
            th = float(t.get('largo', mat.get('tablero_largo_original') or 1))
            scale = min(box_w/tw, box_h/th) * 0.92  # hacer el tablero un poco más pequeño

            # Tablero centrado
            tW = tw*scale
            tH = th*scale
            tX = margin_lr + (box_w - tW)/2
            tY = bottom_reserved + (box_h - tH)/2

            # Helper: hachurado diagonal en un rectángulo (para márgenes)
            def hatch_rect(xh, yh, wh, hh, spacing=6, lw=0.5):
                if wh <= 0 or hh <= 0:
                    return
                if FAST_PDF:
                    # Relleno gris muy suave sin recortes ni múltiples líneas
                    p.saveState()
                    p.setFillGray(0.95)
                    p.rect(xh, yh, wh, hh, stroke=0, fill=1)
                    p.restoreState()
                else:
                    p.saveState()
                    path = p.beginPath()
                    path.rect(xh, yh, wh, hh)
                    p.clipPath(path, stroke=0, fill=0)
                    p.setLineWidth(lw)
                    # Gris claro para no competir con piezas
                    p.setStrokeGray(0.7)
                    # Dibujar líneas 45°
                    import math as _m
                    # Extender para cubrir el área recortada
                    start = -int(hh)
                    end = int(wh) + int(hh)
                    # Limitar número máximo de líneas para rendimiento
                    total_span = max(end - start, 1)
                    max_lines = 400
                    eff_spacing = max(spacing, total_span / max_lines)
                    i = start
                    while i <= end:
                        x1 = xh + i
                        y1 = yh
                        x2 = xh + i + hh
                        y2 = yh + hh
                        p.line(x1, y1, x2, y2)
                        i += eff_spacing
                    p.restoreState()

            # Cabecera del tablero con resumen
            # Línea principal grande con Material y contador de tablero dentro del material (i/n)
            p.setFont("Helvetica-Bold", 14)
            header_title = (mat.get('material') or {}).get('nombre') or 'Material'
            titulo_tablero = f"Material {m_idx}: {header_title}  •  Tablero {t_idx}/{total_tabs_mat}"
            p.drawString(30, height-40, titulo_tablero)
            # ID del proyecto en esquina derecha
            try:
                folio_txt = str(getattr(proyecto, 'public_id', '') or '') or getattr(proyecto, 'folio', f"{proyecto.correlativo}-{proyecto.version}")
            except Exception:
                folio_txt = ''
            if folio_txt:
                p.setFont("Helvetica", 9)
                p.drawRightString(width-110, height-40, f"ID: {folio_txt}")  # dejar espacio para el logo
            p.setFont("Helvetica", 10)
            # Recalcular útil desde márgenes para coherencia ante cambios
            effW_mm = max(float(tw) - 2*float(margen_x), 0.0)
            effH_mm = max(float(th) - 2*float(margen_y), 0.0)
            piezas_cnt = len(t.get('piezas') or [])
            # Medidas a los costados: mostrar original y útil (líneas compactas)
            p.drawString(30, height-52, f"{int(tw)}×{int(th)} mm  •  Útil: {int(effW_mm)}×{int(effH_mm)} mm")
            kerf = (mat.get('config') or {}).get('kerf', mat.get('desperdicio_sierra', 0))
            mx = (mat.get('margenes') or {}).get('margen_x', (mat.get('config') or {}).get('margen_x', 0))
            my = (mat.get('margenes') or {}).get('margen_y', (mat.get('config') or {}).get('margen_y', 0))
            p.drawString(40, height-96, f"Piezas: {piezas_cnt}    Kerf: {kerf} mm    Márgenes: x={mx} ; y={my}")
            # Tapacanto: código y ML por tablero
            tap_info_hdr = (mat.get('tapacanto') or {})
            tap_code = tap_info_hdr.get('codigo') or ''
            tap_name = tap_info_hdr.get('nombre') or ''
            # Calcular ML del tapacanto para las piezas de este tablero
            try:
                ml_mm = 0
                for pz in (t.get('piezas') or []):
                    tc = pz.get('tapacantos') or {}
                    if tc.get('arriba'): ml_mm += int(pz.get('ancho',0))
                    if tc.get('abajo'): ml_mm += int(pz.get('ancho',0))
                    if tc.get('derecha'): ml_mm += int(pz.get('largo',0))
                    if tc.get('izquierda'): ml_mm += int(pz.get('largo',0))
                ml_txt = f"{(ml_mm/1000):.2f} m" if ml_mm else "0.00 m"
            except Exception:
                ml_txt = "—"
            # Encabezado: mostrar nombre completo del tapacanto + código
            if tap_name or tap_code:
                full_tap = f"{tap_name} ({tap_code})".strip() if tap_name or tap_code else '—'
                # Si es muy largo, recortar
                try:
                    from reportlab.pdfbase.pdfmetrics import stringWidth
                    maxW = width - 160
                    while stringWidth(f"Tapacanto: {full_tap}  |  ML: {ml_txt}", 'Helvetica', 10) > maxW and len(full_tap) > 3:
                        full_tap = full_tap[:-4] + '…'
                except Exception:
                    pass
                p.drawString(30, height-64, f"Tapacanto: {full_tap}  |  ML: {ml_txt}")
            else:
                p.drawString(30, height-64, f"Tapacanto: —  |  ML: {ml_txt}")
            # Resumen de piezas por tablero
            resumen_items = {}
            for pz in (t.get('piezas') or []):
                nombre = str(pz.get('nombre','Pieza'))
                a = int(pz.get('ancho',0)); l = int(pz.get('largo',0))
                key = (nombre, a, l)
                entry = resumen_items.get(key) or {'count': 0, 'libre': False}
                entry['count'] += 1
                entry['libre'] = entry['libre'] or bool(pz.get('veta_libre'))
                resumen_items[key] = entry
            resumen_list = []
            for (n,a,l), data in resumen_items.items():
                libre_tag = " (Libre)" if data.get('libre') else ""
                resumen_list.append(f"{n}{libre_tag} {a}×{l} × {data['count']}")
            y_summary = height-86
            max_width = (width - 80)
            line = ""; printed = 0
            from reportlab.pdfbase.pdfmetrics import stringWidth
            # Cache simple de widths para evitar recomputar
            cache_w = {}
            for item in sorted(resumen_list):
                s = (item + "; ")
                w_prev = cache_w.get(line, stringWidth(line, 'Helvetica', 9))
                w_s = cache_w.get(s, stringWidth(s, 'Helvetica', 9))
                cache_w[line] = w_prev; cache_w[s] = w_s
                if (w_prev + w_s) > max_width:
                    p.setFont("Helvetica", 9)
                    p.drawString(40, y_summary, line.rstrip())
                    y_summary -= 12
                    line = s
                    printed += 1
                    if printed >= 2:  # limitar a 2 líneas para evitar solapes
                        break
                else:
                    line += s
            if printed < 6 and line:
                p.setFont("Helvetica", 9)
                p.drawString(40, y_summary, line.rstrip(' ;'))

            # Dibujar tablero
            p.setLineWidth(1)
            p.rect(tX, tY, tW, tH)

            # Área útil y márgenes (hachurado diagonal en márgenes)
            effW = effW_mm * scale
            effH = effH_mm * scale
            offX = max(min(margen_x, tw/2.0), 0.0) * scale
            offY_top = max(min(margen_y, th/2.0), 0.0) * scale
            offYBL = tH - (offY_top + effH)

            # Rect de área útil (sin punteado, solo referencia visual opcional)
            # p.rect(tX + offX, tY + offYBL, effW, effH)

            # Márgenes: izquierda, derecha, abajo, arriba
            # Izquierda
            hatch_rect(tX, tY, offX, tH, spacing=6, lw=0.5)
            # Derecha
            hatch_rect(tX + offX + effW, tY, max(tW - (offX + effW), 0), tH, spacing=6, lw=0.5)
            # Abajo
            hatch_rect(tX + offX, tY, effW, max(offYBL, 0), spacing=6, lw=0.5)
            # Arriba
            top_h = max(tH - (offYBL + effH), 0)
            hatch_rect(tX + offX, tY + offYBL + effH, effW, top_h, spacing=6, lw=0.5)

            # Piezas
            # Etiquetado como en el visualizador: usar índices GLOBALES por tipo dentro del material
            # y coordenadas fieles: decidir automáticamente si vienen relativas al área útil
            # o absolutas (incluyendo márgenes), eligiendo el caso que encaja en el área útil.
            piezas_tab = (t.get('piezas') or [])
            # Colecciones para líneas de corte (coordenadas en PDF) y segmentos por eje
            _cut_xs = set()
            _cut_ys = set()
            _vert_segments = {}  # x -> list[(y0,y1)]
            _horiz_segments = {} # y -> list[(x0,x1)]

            # Hachurar el área útil completa (los rectángulos de piezas la "limpiarán" encima)
            try:
                hatch_rect(tX + offX, tY + offYBL, effW, effH, spacing=6, lw=0.5)
            except Exception:
                pass
            for pieza in piezas_tab:
                aN = int(pieza.get('ancho',0)); lN = int(pieza.get('largo',0))
                kN = (pieza.get('nombre'), min(aN,lN), max(aN,lN))
                corridas_global_por_tipo[kN] = corridas_global_por_tipo.get(kN, 0) + 1
                running_tipo = pieza.get('indiceUnidad') or corridas_global_por_tipo[kN]
                total_tipo = pieza.get('totalUnidades') or totales_global_por_tipo.get(kN, 1)
                # Normalización robusta de coordenadas a relativas al área útil
                px_mm = float(pieza.get('x',0)); py_mm = float(pieza.get('y',0))
                pw_mm = float(pieza.get('ancho',0)); ph_mm = float(pieza.get('largo',0))
                mx_val = float(margen_x); my_val = float(margen_y)
                def _fits(rx, ry, eps=2.0):
                    return (
                        rx >= -eps and ry >= -eps and
                        rx + pw_mm <= effW_mm + eps and
                        ry + ph_mm <= effH_mm + eps
                    )
                candA = (px_mm, py_mm)  # asumir ya relativas
                candB = (px_mm - mx_val, py_mm - my_val)  # asumir absolutas con margen
                # Preferimos la que mejor encaje dentro del área útil
                if _fits(candB[0], candB[1], eps=2.0):
                    px_rel_mm, py_rel_mm = candB
                elif _fits(candA[0], candA[1], eps=2.0):
                    px_rel_mm, py_rel_mm = candA
                else:
                    # En última instancia, usar B y recortar a límites [0, útil]
                    rx, ry = candB
                    rx = max(0.0, min(rx, max(effW_mm - pw_mm, 0.0)))
                    ry = max(0.0, min(ry, max(effH_mm - ph_mm, 0.0)))
                    px_rel_mm, py_rel_mm = rx, ry

                px = px_rel_mm * scale
                py = py_rel_mm * scale
                w = pw_mm * scale
                h = ph_mm * scale
                x = tX + offX + px
                y = tY + offYBL + (effH - (py + h))
                # Rectángulo de la pieza: sin borde; relleno blanco para tapar hachurado y cualquier kerf subyacente
                p.setFillGray(1.0)
                p.rect(x, y, w, h, stroke=0, fill=1)
                # Etiquetas mínimas: siempre a lo largo de la pieza para no invadir adyacentes
                nombre = str(pieza.get('nombre','Pieza'))
                pa = int(pieza.get('ancho',0)); pl = int(pieza.get('largo',0))
                rot = ' ↻' if pieza.get('rotada') else ''
                et1 = f"{nombre} ({running_tipo}/{total_tipo}){rot}"
                et2 = f"{pa}×{pl} mm"
                try:
                    from reportlab.pdfbase.pdfmetrics import stringWidth
                    fs1, fs2 = 7.5, 7
                    # Si la pieza es más alta que ancha, rotamos texto 90° y usamos altura como ancho disponible
                    is_vertical = h >= w
                    maxW = max((h if is_vertical else w) - 6, 10)
                    while fs1 > 4 and stringWidth(et1, 'Helvetica-Bold', fs1) > maxW:
                        fs1 -= 0.5
                    while fs2 > 4 and stringWidth(et2, 'Helvetica', fs2) > maxW:
                        fs2 -= 0.5
                except Exception:
                    fs1, fs2 = 7.5, 7
                    is_vertical = h >= w
                # Clip dentro de la pieza y dibujar el NOMBRE orientado al lado más largo
                p.saveState()
                clip = p.beginPath(); clip.rect(x, y, w, h); p.clipPath(clip, stroke=0, fill=0)
                p.setFillGray(0)
                try:
                    from reportlab.pdfbase.pdfmetrics import stringWidth
                    # Determinar orientación por el lado más largo
                    orient_vertical = h >= w
                    # Limitar tamaño para que el alto de la fuente no supere el lado corto
                    max_font = max(4.0, min(fs1, (min(w, h) - 6) * 0.9))
                    fs_name = max_font
                    # Ajustar a lo largo del lado largo disponible (-6 de margen)
                    max_run = max((h if orient_vertical else w) - 6, 8)
                    while fs_name > 4 and stringWidth(et1, 'Helvetica-Bold', fs_name) > max_run:
                        fs_name -= 0.5
                    p.setFont('Helvetica-Bold', fs_name)
                    cx, cy = (x + w/2.0, y + h/2.0)
                    if orient_vertical:
                        p.saveState()
                        p.translate(cx, cy)
                        p.rotate(90)
                        # Centrado perfecto tras la rotación
                        p.drawCentredString(0, -fs_name/3.0, et1)
                        p.restoreState()
                    else:
                        p.drawCentredString(cx, cy - fs_name/3.0, et1)
                except Exception:
                    try:
                        p.setFont('Helvetica-Bold', fs1)
                        p.drawCentredString(x + w/2.0, y + h/2.0, et1)
                    except Exception:
                        pass

                # Mostrar medidas en los lados: ancho (pa) en el lado superior/central horizontal,
                # y alto (pl) en el lado derecho/central vertical, siguiendo la línea (rotado 90°).
                label_w = f"{pa} mm"
                label_h = f"{pl} mm"
                # Ajustar tamaño de fuente para que quepa en la longitud del lado
                try:
                    from reportlab.pdfbase.pdfmetrics import stringWidth
                    # Fuente inicial
                    fw = fs2
                    fh = fs2
                    max_w_w = max(w - 6, 6)
                    max_w_h = max(h - 6, 6)
                    # Reducir fuente si no cabe en la dimensión disponible
                    while fw > 4 and stringWidth(label_w, 'Helvetica', fw) > max_w_w:
                        fw -= 0.5
                    while fh > 4 and stringWidth(label_h, 'Helvetica', fh) > max_w_h:
                        fh -= 0.5
                except Exception:
                    fw = fs2; fh = fs2

                # Dibujar label horizontal (ancho) cerca del borde superior interno
                try:
                    p.setFont('Helvetica', fw)
                    y_label = y + h - (fw + 2)
                    p.drawCentredString(x + w/2, y_label, label_w)
                except Exception:
                    pass

                # Dibujar label vertical (alto) en el lado derecho, rotado 90° y centrado verticalmente
                try:
                    p.saveState()
                    p.setFont('Helvetica', fh)
                    # Punto de referencia: un poco dentro del borde derecho
                    rx = x + w - (fh/2) - 2
                    ry = y + h/2
                    p.translate(rx, ry)
                    p.rotate(90)
                    # Tras rotar, centrar en X=0
                    p.drawCentredString(0, 0, label_h)
                    p.restoreState()
                except Exception:
                    try:
                        p.restoreState()
                    except Exception:
                        pass

                p.restoreState()

                # Tapacantos internos: líneas punteadas por dentro de la pieza
                taps = pieza.get('tapacantos') or {}
                if any(taps.values()):
                    p.saveState()
                    # Rojo similar al del visualizador (#dc3545)
                    p.setStrokeColorRGB(220/255.0, 53/255.0, 69/255.0)
                    p.setLineWidth(1.2)
                    p.setDash(3, 2)
                    # ~6.0 mm hacia adentro para mayor separación respecto al borde
                    inset = 6.0 * scale
                    inset = max(0.5, min(inset, (min(w, h) / 2.0) - 0.5))
                    # Arriba
                    if taps.get('arriba'):
                        p.line(x + inset, y + h - inset, x + w - inset, y + h - inset)
                    # Abajo
                    if taps.get('abajo'):
                        p.line(x + inset, y + inset, x + w - inset, y + inset)
                    # Izquierda
                    if taps.get('izquierda'):
                        p.line(x + inset, y + inset, x + inset, y + h - inset)
                    # Derecha
                    if taps.get('derecha'):
                        p.line(x + w - inset, y + inset, x + w - inset, y + h - inset)
                    p.restoreState()
                # Registrar bordes para líneas de corte globales y segmentos útiles (solo sobre rango de piezas)
                try:
                    # Normalizar con redondeo para agrupar flotantes cercanos
                    rx0 = round(float(x), 2); rx1 = round(float(x + w), 2)
                    ry0 = round(float(y), 2); ry1 = round(float(y + h), 2)
                    _cut_xs.add(rx0); _cut_xs.add(rx1)
                    _cut_ys.add(ry0); _cut_ys.add(ry1)
                    _vert_segments.setdefault(rx0, []).append((ry0, ry1))
                    _vert_segments.setdefault(rx1, []).append((ry0, ry1))
                    _horiz_segments.setdefault(ry0, []).append((rx0, rx1))
                    _horiz_segments.setdefault(ry1, []).append((rx0, rx1))
                except Exception:
                    pass

            # Dibujar líneas de corte (kerf) como segmentos continuos SOLO donde hay piezas;
            # trazo continuo (sin dash) y grosor proporcional al kerf.
            try:
                p.saveState()
                # Grosor del kerf en puntos PDF
                try:
                    kerf_mm = float((mat.get('config') or {}).get('kerf', mat.get('desperdicio_sierra', 0)) or 0)
                except Exception:
                    kerf_mm = 0.0
                lw = max(0.6, min(3.0, kerf_mm * float(scale)))
                p.setLineWidth(lw)
                p.setStrokeGray(0.15)
                # Sin dash: línea normal continua
                # Limitar a área útil para no marcar en puro desperdicio
                x_min = tX + offX + 0.1
                x_max = tX + offX + effW - 0.1
                y_min = tY + offYBL + 0.1
                y_max = tY + offYBL + effH - 0.1
                # Verticales: para cada x, dibujar desde min(y0) a max(y1) dentro de útil
                for cx, segs in _vert_segments.items():
                    if cx <= x_min or cx >= x_max:
                        # Evitar dibujar exactamente en el borde útil
                        continue
                    ymin = min((s for s,_ in segs), default=None)
                    ymax = max((e for _,e in segs), default=None)
                    if ymin is None or ymax is None:
                        continue
                    y0 = max(y_min, ymin)
                    y1 = min(y_max, ymax)
                    if y1 - y0 > 0.5:
                        p.line(cx, y0, cx, y1)
                # Horizontales
                for cy, segs in _horiz_segments.items():
                    if cy <= y_min or cy >= y_max:
                        continue
                    xmin = min((s for s,_ in segs), default=None)
                    xmax = max((e for _,e in segs), default=None)
                    if xmin is None or xmax is None:
                        continue
                    x0 = max(x_min, xmin)
                    x1 = min(x_max, xmax)
                    if x1 - x0 > 0.5:
                        p.line(x0, cy, x1, cy)
                p.restoreState()
            except Exception:
                try:
                    p.restoreState()
                except Exception:
                    pass

            # En esta sección ya no se imprime tabla inferior; se dedica toda la página al tablero
            p.showPage()

        # Tras imprimir los tableros de este material, agregar hoja(s) resumen del material
        # 1) Resumen general del material + (en la misma hoja) resumen de piezas por tablero
        draw_logo(width-40, height-40)
        p.setFont('Helvetica-Bold', 13)
        mat_title = (mat.get('material') or {}).get('nombre') or 'Material'
        p.drawString(30, height-40, f"Resumen Material {m_idx}: {mat_title}")
        # Datos generales del material
        try:
            orig_w = int(mat.get('tablero_ancho_original', (mat.get('material') or {}).get('ancho_original', 0)))
            orig_h = int(mat.get('tablero_largo_original', (mat.get('material') or {}).get('largo_original', 0)))
            mx = int((mat.get('margenes') or {}).get('margen_x', (mat.get('config') or {}).get('margen_x', 0)))
            my = int((mat.get('margenes') or {}).get('margen_y', (mat.get('config') or {}).get('margen_y', 0)))
            util_w = max(0, orig_w - 2*mx)
            util_h = max(0, orig_h - 2*my)
        except Exception:
            orig_w = orig_h = util_w = util_h = mx = my = 0
        tap_info = mat.get('tapacanto') or {}
        tap_txt = (f"{tap_info.get('nombre','')} ({tap_info.get('codigo','')})".strip() if (tap_info.get('nombre') or tap_info.get('codigo')) else '—')
        p.setFont('Helvetica', 10)
        p.drawString(30, height-60, f"Tableros: {len(mat.get('tableros') or [])}")
        p.drawString(150, height-60, f"Medidas tablero: {orig_w}×{orig_h} mm  |  Útil: {util_w}×{util_h} mm (mx={mx}, my={my})")
        p.drawString(30, height-76, f"Tapacanto: {tap_txt}")

        # Tabla de todas las piezas del material (agregada por tipo)
        def _agregar_por_tipo(mat):
            agg = {}
            for t in (mat.get('tableros') or []):
                for pz in (t.get('piezas') or []):
                    key = (pz.get('nombre'), int(pz.get('ancho',0)), int(pz.get('largo',0)))
                    item = agg.get(key) or {'nombre': key[0], 'ancho': key[1], 'largo': key[2], 'cantidad': 0}
                    item['cantidad'] += 1
                    agg[key] = item
            return sorted(agg.values(), key=lambda r: (r['nombre'], r['ancho'], r['largo']))

        rows = _agregar_por_tipo(mat)
        ycur = height-100
        draw_table_header(ycur, [("Pieza",180),("Cantidad",80),("Ancho",80),("Alto",80)])
        ycur -= 18
        p.setFont('Helvetica', 9)
        for r in rows:
            if ycur < 60:
                p.showPage(); draw_logo(width-40, height-40)
                p.setFont('Helvetica-Bold', 12); p.drawString(30, height-40, f"Resumen Material {m_idx}: {mat_title} (cont.)")
                ycur = height-70
                draw_table_header(ycur, [("Pieza",180),("Cantidad",80),("Ancho",80),("Alto",80)])
                ycur -= 18
                p.setFont('Helvetica', 9)
            x = 30
            p.drawString(x, ycur, str(r['nombre'])); x += 180
            p.drawString(x, ycur, str(r['cantidad'])); x += 80
            p.drawString(x, ycur, str(r['ancho'])); x += 80
            p.drawString(x, ycur, str(r['largo']))
            ycur -= 12

        # 2) Una o más tablas por tablero: piezas que contiene, cantidad, ancho, alto, si lleva tapacanto y lados
        def _label_lados_tuple(lados_tuple):
            try:
                if not lados_tuple:
                    return '—'
                # Usar iniciales compactas para evitar solapes en la tabla resumen
                orden = ['arriba','derecha','abajo','izquierda']
                iniciales = {'arriba':'A','derecha':'D','abajo':'B','izquierda':'I'}
                parts = [iniciales[k] for k in orden if k in set(lados_tuple)]
                return '—' if not parts else ','.join(parts)
            except Exception:
                return '—'

        # 2) Resumen por tablero (dos tablas paralelas, compactas)
        # Configuración de columnas compactas
        left_x = 30
        gap_x = 20
        table_w = (width - 2*left_x - gap_x) / 2.0  # ancho de cada tabla
        cols = [("Pieza", 140), ("Cant.", 40), ("Ancho", 60), ("Alto", 60), ("Tapacanto", table_w - (140+40+60+60))]
        row_h = 11  # altura de fila compacta

        col_idx = 0  # 0: izquierda, 1: derecha
        col_x = [left_x, left_x + table_w + gap_x]
        col_y = [ycur, ycur]

        for t_idx2, t2 in enumerate(tableros_mat, start=1):
            # Decidir la columna donde dibujar este tablero
            x0 = col_x[col_idx]
            y0 = col_y[col_idx]

            # Si no hay espacio suficiente para el título + cabecera + al menos 1 fila, saltar página y resetear columnas
            min_block_h = 14 + 15 + row_h  # título + cabecera + 1 fila
            if y0 < 40 + min_block_h:
                p.showPage(); draw_logo(width-40, height-40)
                p.setFont('Helvetica-Bold', 12); p.drawString(30, height-40, f"Resumen Material {m_idx}: {mat_title} (cont.)")
                # resetear columnas al tope
                col_y = [height-70, height-70]
                y0 = col_y[col_idx]

            # Título del tablero (separado del bloque superior por el salto lógico previo; aquí pegado a su propia tabla)
            p.setFont('Helvetica-Bold', 11)
            p.drawString(x0, y0, f"Tablero {t_idx2}/{total_tabs_mat}")
            y0 -= 14

            # Agrupar filas del tablero actual
            grupos = {}
            for pz in (t2.get('piezas') or []):
                key = (pz.get('nombre'), int(pz.get('ancho',0)), int(pz.get('largo',0)), tuple(sorted([k for k,v in (pz.get('tapacantos') or {}).items() if v])))
                it = grupos.get(key) or {
                    'nombre': key[0], 'ancho': key[1], 'largo': key[2], 'cantidad': 0,
                    'tapacanto': _label_lados_tuple(key[3])
                }
                it['cantidad'] += 1
                grupos[key] = it
            filas = sorted(grupos.values(), key=lambda r: (r['nombre'], r['ancho'], r['largo']))

            # Cabecera en la columna
            draw_table_header_at(x0, y0, cols, table_w)
            y0 -= 15
            p.setFont('Helvetica', 8.8)

            # Filas compactas sin espaciado extra entre líneas
            for row in filas:
                # Si no cabe en la columna actual, pasar a la otra columna o nueva página si ya estamos en derecha
                if y0 < 40 + row_h:
                    if col_idx == 0:
                        # Pasar a la columna derecha, usando su y actual
                        col_idx = 1
                        x0 = col_x[col_idx]
                        y0 = col_y[col_idx]
                        # Asegurar espacio en la derecha; si no hay, nueva página
                        if y0 < 40 + (14 + 15 + row_h):
                            p.showPage(); draw_logo(width-40, height-40)
                            p.setFont('Helvetica-Bold', 12); p.drawString(30, height-40, f"Resumen Material {m_idx}: {mat_title} (cont.)")
                            col_y = [height-70, height-70]
                            y0 = col_y[col_idx]
                        # Redibujar título y cabecera en la nueva columna
                        p.setFont('Helvetica-Bold', 11)
                        p.drawString(x0, y0, f"Tablero {t_idx2}/{total_tabs_mat}"); y0 -= 14
                        draw_table_header_at(x0, y0, cols, table_w); y0 -= 15
                        p.setFont('Helvetica', 8.8)
                    else:
                        # Ya estamos en derecha -> nueva página y reset de ambas columnas
                        p.showPage(); draw_logo(width-40, height-40)
                        p.setFont('Helvetica-Bold', 12); p.drawString(30, height-40, f"Resumen Material {m_idx}: {mat_title} (cont.)")
                        col_y = [height-70, height-70]
                        # Continuar en izquierda (más natural)
                        col_idx = 0
                        x0 = col_x[col_idx]
                        y0 = col_y[col_idx]
                        # Redibujar título y cabecera
                        p.setFont('Helvetica-Bold', 11)
                        p.drawString(x0, y0, f"Tablero {t_idx2}/{total_tabs_mat}"); y0 -= 14
                        draw_table_header_at(x0, y0, cols, table_w); y0 -= 15
                        p.setFont('Helvetica', 8.8)

                # Dibujar la fila
                x = x0
                p.drawString(x, y0, str(row['nombre'])); x += cols[0][1]
                p.drawString(x, y0, str(row['cantidad'])); x += cols[1][1]
                p.drawString(x, y0, str(row['ancho'])); x += cols[2][1]
                p.drawString(x, y0, str(row['largo'])); x += cols[3][1]
                p.drawString(x, y0, row.get('tapacanto','—'))
                y0 -= row_h

            # Guardar la Y final de esta columna y alternar columna para el siguiente tablero
            col_y[col_idx] = y0 - 6  # pequeño colchón entre tablas dentro de la misma columna
            col_idx = 1 - col_idx
        # Ajustar ycur al mínimo de ambas columnas para no interferir con el salto final
        ycur = min(col_y)

        # Asegurar separación: tras terminar el resumen del material actual,
        # forzar salto de página si no es el último material, para que
        # el próximo bloque de tableros comience en una página nueva.
        try:
            if m_idx < len(materiales):
                p.showPage()
        except Exception:
            # Si por alguna razón no podemos evaluar la longitud, 
            # no forzar salto adicional para evitar página en blanco final.
            pass

    p.save()
    data = buf.getvalue(); buf.close(); return data

# ------------------------------
# Utilidades: reconstrucción del resultado desde configuración
# ------------------------------
def _optimizar_desde_conf_mat(conf_mat: dict, piezas_in: list):
    """Ejecuta el motor de optimización para un material+lista de piezas del payload de configuración."""
    if not (conf_mat and piezas_in and conf_mat.get('material_id')):
        return None
    material_id = conf_mat.get('material_id')
    material = get_object_or_404(Material, id=material_id)
    ancho_tablero = conf_mat.get('ancho_custom') or material.ancho
    largo_tablero = conf_mat.get('largo_custom') or material.largo
    margen_x = conf_mat.get('margen_x', 0)
    margen_y = conf_mat.get('margen_y', 0)
    desperdicio_sierra = conf_mat.get('desperdicio_sierra', 3)
    tapacanto_codigo = conf_mat.get('tapacanto_codigo', '')
    tapacanto_nombre = conf_mat.get('tapacanto_nombre', '')
    engine = OptimizationEngine(ancho_tablero, largo_tablero, margen_x, margen_y, desperdicio_sierra)
    piezas_proc = []
    for p in piezas_in:
        piezas_proc.append({
            'nombre': p['nombre'],
            'ancho': p['ancho'],
            'largo': p['largo'],
            'cantidad': p.get('cantidad', 1),
            'veta_libre': p.get('veta_libre', False),
            'tapacantos': p.get('tapacantos', {}) or {}
        })
    r = engine.optimizar_piezas(piezas_proc)
    r['entrada'] = piezas_proc
    r['material'] = {
        'nombre': material.nombre,
        'codigo': material.codigo,
        'ancho_original': material.ancho,
        'largo_original': material.largo,
        'ancho_usado': ancho_tablero,
        'largo_usado': largo_tablero
    }
    r['config'] = {'margen_x': margen_x, 'margen_y': margen_y, 'kerf': desperdicio_sierra}
    r['tapacanto'] = { 'codigo': tapacanto_codigo, 'nombre': tapacanto_nombre }
    return r

def _resultado_desde_configuracion(proyecto):
    """Intenta construir un resultado completo desde proyecto.configuracion (1 o varios materiales)."""
    if not proyecto.configuracion:
        return None
    try:
        cfg = json.loads(proyecto.configuracion) if isinstance(proyecto.configuracion, str) else proyecto.configuracion
    except Exception:
        return None

    materiales = []
    try:
        if isinstance(cfg, dict) and isinstance(cfg.get('materiales'), list):
            for mcfg in cfg['materiales']:
                conf_mat = mcfg.get('configuracion_material') or mcfg.get('config')
                piezas_in = mcfg.get('piezas') or mcfg.get('entrada')
                r = _optimizar_desde_conf_mat(conf_mat, piezas_in)
                if r:
                    materiales.append(r)
        else:
            conf_mat = cfg.get('configuracion_material') or cfg.get('config')
            piezas_in = cfg.get('piezas') or cfg.get('entrada')
            r = _optimizar_desde_conf_mat(conf_mat, piezas_in)
            if r:
                materiales.append(r)
    except Exception:
        return None

    if not materiales:
        return None

    total_tableros = sum(len(m.get('tableros', [])) for m in materiales)
    total_piezas = sum(sum(len(t.get('piezas', [])) for t in m.get('tableros', [])) for m in materiales)
    eficiencias = [m.get('eficiencia') or m.get('eficiencia_promedio') for m in materiales if m]
    eff_vals = [e for e in eficiencias if e]
    eficiencia_promedio = (sum(eff_vals) / len(eff_vals)) if eff_vals else 0
    folio = f"OPT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    resultado_persist = {
        'materiales': materiales,
        'total_tableros': total_tableros,
        'total_piezas': total_piezas,
        'eficiencia_promedio': eficiencia_promedio,
        'ultimo_folio': folio,
        'historial': [{
            'folio': folio,
            'fecha': datetime.now().isoformat(),
            'materiales': materiales,
            'total_tableros': total_tableros,
            'total_piezas': total_piezas,
            'eficiencia_promedio': eficiencia_promedio,
        }]
    }
    return resultado_persist

@login_required
def optimizador_home_nuevo(request):
    """Alias: redirige a la versión clásica (hoja final)."""
    return redirect('optimizador_home')

@login_required
def optimizador_home(request):
    """Vista principal del optimizador. Por ahora redirige a la versión clásica."""
    return optimizador_home_clasico(request)

def optimizador_home_test(request):
    """Vista de prueba del optimizador (sin auth en urls se marca temporal)."""
    return optimizador_home_clasico(request)

def js_test(request):
    """Vista de test de JavaScript simple."""
    return HttpResponse("OK")

@login_required
def optimizador_abrir(request, proyecto_id:int):
    """Abrir el optimizador precargando un proyecto existente (por id)."""
    try:
        # Validar existencia (y permisos) de proyecto, pero no cargar aquí la data
        get_object_or_404(Proyecto, id=proyecto_id)
        # Redirigir con query param para que el frontend se encargue de cargar datos
        return redirect(f"{reverse('optimizador_home')}?proyecto_id={proyecto_id}")
    except Exception:
        return redirect('optimizador_home')

@login_required
def preview_proyecto_json(request, proyecto_id:int):
    """Stub: devuelve un JSON básico de preview para el modal de organización."""
    try:
        proyecto = get_object_or_404(Proyecto, id=proyecto_id)
        resumen = {
            'success': True,
            'proyecto': {
                'codigo': proyecto.codigo,
                'nombre': proyecto.nombre,
                'cliente': (proyecto.cliente.nombre if proyecto.cliente_id else '-'),
                'estado': proyecto.estado,
                'fecha': proyecto.fecha_creacion.strftime('%d-%m-%Y %H:%M') if proyecto.fecha_creacion else ''
            }
        }
        return JsonResponse(resumen)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@login_required 
@csrf_exempt
def crear_proyecto_optimizacion(request):
    """Crea un nuevo proyecto de optimización con todos los campos requeridos"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body or '{}')
            nombre = data.get('nombre') or 'Proyecto sin nombre'
            cliente_id = data.get('cliente_id')
            descripcion = data.get('descripcion', '')
            # Solo guardar configuración si viene explícitamente; evitar guardar el payload completo
            configuracion = data.get('configuracion') if isinstance(data.get('configuracion'), (dict, list)) else None

            # Si no llega cliente_id, intentar crear/buscar por nombre+rut
            if not cliente_id:
                nombre_cliente = (data.get('cliente_nombre') or '').strip()
                rut_cliente_raw = (data.get('cliente_rut') or '')
                rut_cliente = _normalize_rut(rut_cliente_raw)
                if nombre_cliente and rut_cliente:
                    # Determinar organización desde el usuario autenticado
                    org = None
                    try:
                        if hasattr(request.user, 'usuarioperfiloptimizador') and request.user.usuarioperfiloptimizador.organizacion:
                            org = request.user.usuarioperfiloptimizador.organizacion
                        elif hasattr(request.user, 'usuario_perfil_optimizador') and request.user.usuario_perfil_optimizador.organizacion:
                            org = request.user.usuario_perfil_optimizador.organizacion
                    except Exception:
                        org = None

                    cliente, creado = Cliente.objects.get_or_create(
                        rut=rut_cliente,
                        defaults={'nombre': nombre_cliente, 'activo': True, 'organizacion': org}
                    )
                    # Si ya existía y no tenía organización, asignarla
                    if not creado and org and not cliente.organizacion:
                        cliente.organizacion = org
                        cliente.save(update_fields=['organizacion'])
                    cliente_id = cliente.id
                else:
                    return JsonResponse({'success': False, 'message': 'cliente_id es requerido'})

            # Generar código único
            base = 'PROJ'
            sec = datetime.now().strftime('%Y%m%d%H%M%S')
            codigo = f"{base}-{sec}"

            # Asignar correlativo único por cliente: max+1
            try:
                ultimo = Proyecto.objects.filter(cliente_id=cliente_id).order_by('-correlativo').first()
                correlativo = (ultimo.correlativo + 1) if ultimo and (ultimo.correlativo is not None) else 1
            except Exception:
                correlativo = 1

            # Determinar siguiente public_id global iniciando en 100
            try:
                ultimo_pub = Proyecto.objects.exclude(public_id__isnull=True).order_by('-public_id').first()
                next_public_id = (ultimo_pub.public_id + 1) if ultimo_pub and ultimo_pub.public_id and ultimo_pub.public_id >= 100 else 100
            except Exception:
                next_public_id = 100

            ctx = get_auth_context(request)
            proyecto = Proyecto.objects.create(
                codigo=codigo,
                nombre=nombre,
                cliente_id=cliente_id,
                descripcion=descripcion,
                estado='borrador',
                fecha_inicio=timezone.now().date(),
                total_materiales=0,
                total_tableros=0,
                total_piezas=0,
                eficiencia_promedio=0,
                costo_total=0,
                usuario=request.user,
                creado_por=request.user,
                configuracion=configuracion,
                correlativo=correlativo,
                version=0,
                public_id=next_public_id,
                organizacion_id=ctx.get('organization_id'),
            )
            # Auditoría de creación de proyecto
            try:
                AuditLog.objects.create(
                    actor=request.user,
                    organizacion=proyecto.organizacion,
                    verb='CREATE',
                    target_model='Proyecto',
                    target_id=str(proyecto.id),
                    target_repr=f"{proyecto.codigo} - {proyecto.nombre}",
                    changes={'cliente_id': cliente_id}
                )
            except Exception:
                pass

            return JsonResponse({
                'success': True,
                'proyecto_id': proyecto.id,
                'codigo': proyecto.codigo,
                'folio': str(proyecto.public_id) if proyecto.public_id else getattr(proyecto, 'folio', f"{proyecto.correlativo}-{proyecto.version}"),
                'message': 'Proyecto creado exitosamente'
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al crear proyecto: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': 'Método no permitido'})

@login_required
@csrf_exempt  
def optimizar_material(request):
    """Ejecuta la optimización del material"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Obtener configuración del material
            config = data['configuracion_material']
            material_id = config['material_id']
            material = get_object_or_404(Material, id=material_id)
            
            # Dimensiones del tablero - SIEMPRE usar las medidas de los campos editables
            # Estas son la fuente de verdad para la optimización
            ancho_tablero = config.get('ancho_custom') or material.ancho
            largo_tablero = config.get('largo_custom') or material.largo
            
            print(f"Optimización usando dimensiones del tablero: {ancho_tablero}mm x {largo_tablero}mm")
            print(f"Material original: {material.ancho}mm x {material.largo}mm")
            
            # Parámetros de optimización
            margen_x = config.get('margen_x', 0)
            margen_y = config.get('margen_y', 0)
            desperdicio_sierra = config.get('desperdicio_sierra', 3)
            tapacanto_codigo = config.get('tapacanto_codigo', '')
            tapacanto_nombre = config.get('tapacanto_nombre', '')
            
            # Crear motor de optimización
            engine = OptimizationEngine(
                ancho_tablero, largo_tablero,
                margen_x, margen_y, desperdicio_sierra
            )
            
            # Procesar piezas
            piezas = data['piezas']
            piezas_procesadas = []
            
            for pieza in piezas:
                piezas_procesadas.append({
                    'nombre': pieza['nombre'],
                    'ancho': pieza['ancho'],
                    'largo': pieza['largo'],
                    'cantidad': pieza['cantidad'],
                    'veta_libre': pieza.get('veta_libre', False),
                    'tapacantos': pieza.get('tapacantos', [])
                })
            
            # Ejecutar optimización
            resultado = engine.optimizar_piezas(piezas_procesadas)
            # Conservar entrada original de piezas para futura rehidratación fiel de la grilla
            try:
                resultado['entrada'] = piezas_procesadas
            except Exception:
                pass
            
            # Agregar información del material
            resultado['material'] = {
                'nombre': material.nombre,
                'codigo': material.codigo,
                'ancho_original': material.ancho,
                'largo_original': material.largo,
                'ancho_usado': ancho_tablero,
                'largo_usado': largo_tablero
            }
            # Metadatos de tapacanto a nivel de material
            resultado['tapacanto'] = {
                'codigo': tapacanto_codigo,
                'nombre': tapacanto_nombre,
            }
            
            # Guardar/Acumular resultado si hay proyecto_id
            if data.get('proyecto_id'):
                proyecto = get_object_or_404(Proyecto, id=data['proyecto_id'])
                existente = {}
                try:
                    if proyecto.resultado_optimizacion:
                        existente = json.loads(proyecto.resultado_optimizacion)
                except Exception:
                    existente = {}

                # Si el frontend indicó reset total, descartar resultado previo
                try:
                    if data.get('resetear_resultado'):
                        existente = {}
                except Exception:
                    pass

                materiales = existente.get('materiales', [])
                material_index = data.get('material_index', 1)

                # Enriquecer resultado con metadatos del material
                resultado['material_index'] = material_index
                resultado['config'] = {
                    'margen_x': margen_x,
                    'margen_y': margen_y,
                    'kerf': desperdicio_sierra,
                }
                # Guardar también el tapacanto de esta pestaña/material
                resultado['tapacanto'] = {
                    'codigo': tapacanto_codigo,
                    'nombre': tapacanto_nombre,
                }

                # Reemplazar si ya existe ese índice, si no, agregar
                reemplazado = False
                for i, m in enumerate(materiales):
                    if m.get('material_index') == material_index:
                        materiales[i] = resultado
                        reemplazado = True
                        break
                if not reemplazado:
                    materiales.append(resultado)

                # Actualizar totales del proyecto
                total_tableros = sum(len(m.get('tableros', [])) for m in materiales)
                total_piezas = sum(sum(len(t.get('piezas', [])) for t in m.get('tableros', [])) for m in materiales)
                eficiencias = [m.get('eficiencia_promedio') or m.get('eficiencia') for m in materiales if m]
                eficiencia_promedio = sum(eficiencias)/len(eficiencias) if eficiencias else 0

                existente['materiales'] = materiales
                existente['total_tableros'] = total_tableros
                existente['total_piezas'] = total_piezas
                existente['eficiencia_promedio'] = eficiencia_promedio

                # Snapshot del historial se agregará luego de asignar el nuevo ID público

                # Persistir resultado y actualizar configuración del proyecto para soportar forzar_optimizacion
                try:
                    # Construir configuración agregada (multi-material) mínima
                    cfg_actual = None
                    # Rehidratar desde lo que exista
                    try:
                        cfg_actual = json.loads(proyecto.configuracion) if proyecto.configuracion else None
                    except Exception:
                        cfg_actual = None
                    # Normalizar a lista de materiales
                    materiales_cfg = []
                    if isinstance(cfg_actual, dict) and isinstance(cfg_actual.get('materiales'), list):
                        materiales_cfg = cfg_actual['materiales']
                    elif isinstance(cfg_actual, dict) and (cfg_actual.get('configuracion_material') or cfg_actual.get('config')):
                        materiales_cfg = [cfg_actual]
                    # Payload de configuración para el material actual
                    mat_cfg_payload = {
                        'configuracion_material': {
                            'material_id': material_id,
                            'ancho_custom': ancho_tablero,
                            'largo_custom': largo_tablero,
                            'margen_x': margen_x,
                            'margen_y': margen_y,
                            'desperdicio_sierra': desperdicio_sierra,
                            'tapacanto_codigo': tapacanto_codigo,
                            'tapacanto_nombre': tapacanto_nombre,
                        },
                        'piezas': piezas_procesadas,
                    }
                    # Insertar/reemplazar por índice de material
                    idx_um = max(0, int(material_index) - 1)
                    while len(materiales_cfg) <= idx_um:
                        materiales_cfg.append({})
                    materiales_cfg[idx_um] = mat_cfg_payload
                    cfg_agg = { 'materiales': materiales_cfg }
                    proyecto.configuracion = json.dumps(cfg_agg, ensure_ascii=False)
                except Exception:
                    pass

                # Incrementar versión y asignar SIEMPRE un nuevo ID público (nuevo ID por cada optimización)
                try:
                    proyecto.version = (proyecto.version or 0) + 1
                except Exception:
                    proyecto.version = 1
                # Calcular el siguiente public_id global (mínimo 100)
                try:
                    ultimo_pub = Proyecto.objects.exclude(public_id__isnull=True).order_by('-public_id').first()
                    next_public_id = (ultimo_pub.public_id + 1) if ultimo_pub and ultimo_pub.public_id and ultimo_pub.public_id >= 100 else 100
                except Exception:
                    next_public_id = 100
                proyecto.public_id = next_public_id
                existente['folio_proyecto'] = str(proyecto.public_id)
                # Agregar snapshot al historial con el nuevo ID
                try:
                    snapshot = {
                        'folio': str(proyecto.public_id),
                        'fecha': datetime.now().isoformat(),
                        'materiales': materiales,
                        'total_tableros': total_tableros,
                        'total_piezas': total_piezas,
                        'eficiencia_promedio': eficiencia_promedio,
                    }
                    historial = existente.get('historial') or []
                    historial.append(snapshot)
                    if len(historial) > 20:
                        historial = historial[-20:]
                    existente['historial'] = historial
                    existente['ultimo_folio'] = str(proyecto.public_id)
                except Exception:
                    pass
                proyecto.resultado_optimizacion = json.dumps(existente)
                proyecto.total_materiales = len(materiales)
                proyecto.total_tableros = total_tableros
                proyecto.total_piezas = total_piezas
                proyecto.eficiencia_promedio = eficiencia_promedio
                proyecto.estado = 'optimizado'
                proyecto.save()

                # Registrar ejecución y auditoría
                try:
                    OptimizationRun.objects.create(
                        organizacion=proyecto.organizacion,
                        proyecto=proyecto,
                        run_by=request.user,
                        porcentaje_uso=eficiencia_promedio,
                        tiempo_ms=int(resultado.get('tiempo_optimizacion', 0) * 1000) if resultado.get('tiempo_optimizacion') else None,
                    )
                    AuditLog.objects.create(
                        actor=request.user,
                        organizacion=proyecto.organizacion,
                        verb='RUN_OPT',
                        target_model='Proyecto',
                        target_id=str(proyecto.id),
                        target_repr=proyecto.codigo,
                        changes={'material_id': material_id}
                    )
                except Exception:
                    pass

                # Generar y persistir un PDF del layout inmediatamente después de optimizar
                try:
                    from django.conf import settings
                    import os
                    pdf_data = _pdf_from_result(proyecto, existente)

                    # Nombrar por ID del proyecto y nombre del cliente para fácil recuperación
                    folio_actual = str(proyecto.public_id) if proyecto.public_id else f"{proyecto.correlativo}-{proyecto.version}"
                    try:
                        cliente_slug = slugify(proyecto.cliente.nombre) if proyecto.cliente_id else 'cliente'
                    except Exception:
                        cliente_slug = 'cliente'
                    rel_dir = f"proyectos/{proyecto.id}"
                    rel_path = f"{rel_dir}/optimizacion_{folio_actual}_{cliente_slug}.pdf"
                    abs_dir = os.path.join(settings.MEDIA_ROOT, rel_dir)
                    os.makedirs(abs_dir, exist_ok=True)
                    abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)
                    with open(abs_path, 'wb') as fh:
                        fh.write(pdf_data)
                    proyecto.archivo_pdf = rel_path
                    proyecto.save(update_fields=['archivo_pdf'])
                except Exception:
                    # Si falla la generación del PDF, no romper el flujo de optimización
                    pass
            
            resp = {
                'success': True,
                'resultado': resultado
            }
            try:
                if data.get('proyecto_id'):
                    resp['proyecto_id'] = data.get('proyecto_id')
                    # incluir ID actualizado (usamos clave 'folio' por compatibilidad del frontend)
                    try:
                        resp['folio'] = str(proyecto.public_id) if proyecto.public_id else f"{proyecto.correlativo}-{proyecto.version}"
                    except Exception:
                        pass
            except Exception:
                pass
            return JsonResponse(resp)
            
        except Exception as e:
            import traceback
            print(f"Error en optimización: {str(e)}")
            print(traceback.format_exc())
            return JsonResponse({
                'success': False,
                'message': f'Error en la optimización: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})

@login_required
def obtener_material_info(request, material_id):
    """Obtiene información detallada de un material"""
    try:
        material = get_object_or_404(Material, id=material_id)
        
        return JsonResponse({
            'success': True,
            'material': {
                'id': material.id,
                'nombre': material.nombre,
                'codigo': material.codigo,
                'ancho': material.ancho,
                'largo': material.largo,
                'espesor': material.espesor,
                'tipo': material.tipo,
                'precio': float(material.precio) if material.precio else 0
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al obtener información del material: {str(e)}'
        })

@login_required
def exportar_json_entrada(request, proyecto_id):
    """Exporta la configuración de entrada en formato JSON"""
    try:
        proyecto = get_object_or_404(Proyecto, id=proyecto_id)
        
        if not proyecto.configuracion:
            messages.error(request, 'No hay configuración para exportar')
            return redirect('optimizador_home')
        
        configuracion = json.loads(proyecto.configuracion)
        
        response = HttpResponse(
            json.dumps(configuracion, indent=2, ensure_ascii=False),
            content_type='application/json; charset=utf-8'
        )
        response['Content-Disposition'] = f'attachment; filename="config_{proyecto.nombre}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json"'
        
        return response
        
    except Exception as e:
        messages.error(request, f'Error al exportar configuración: {str(e)}')
        return redirect('optimizador_home')

@login_required  
def exportar_json_salida(request, proyecto_id):
    """Exporta el resultado de optimización en formato JSON"""
    try:
        proyecto = get_object_or_404(Proyecto, id=proyecto_id)
        
        if not proyecto.resultado_optimizacion:
            # No redirigir al optimizador; devolver mensaje de error simple
            return HttpResponse('No hay resultado de optimización para exportar', status=400, content_type='text/plain; charset=utf-8')
        
        resultado = json.loads(proyecto.resultado_optimizacion)
        
        response = HttpResponse(
            json.dumps(resultado, indent=2, ensure_ascii=False),
            content_type='application/json; charset=utf-8'
        )
        response['Content-Disposition'] = f'attachment; filename="resultado_{proyecto.nombre}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json"'
        
        return response
        
    except Exception as e:
        messages.error(request, f'Error al exportar resultado: {str(e)}')
        return redirect('optimizador_home')

@login_required
def exportar_pdf(request, proyecto_id):
    """Devuelve el PDF guardado; si falta, lo regenera desde resultado_optimizacion y lo guarda."""
    proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    from django.conf import settings
    import os

    # Priorizar servir el PDF del ID del proyecto si existe (rápido y consistente)
    try:
        folio_actual = str(proyecto.public_id) if proyecto.public_id else f"{proyecto.correlativo}-{proyecto.version}"
    except Exception:
        folio_actual = None

    from django.conf import settings
    import os
    if folio_actual:
        rel_dir = f"proyectos/{proyecto.id}"
        # Primero buscar con cliente en nombre
        try:
            cliente_slug = slugify(proyecto.cliente.nombre) if proyecto.cliente_id else 'cliente'
        except Exception:
            cliente_slug = 'cliente'
        rel_path1 = f"{rel_dir}/optimizacion_{folio_actual}_{cliente_slug}.pdf"
        abs_path1 = os.path.join(settings.MEDIA_ROOT, rel_path1)
        rel_path2 = f"{rel_dir}/optimizacion_{folio_actual}.pdf"
        abs_path2 = os.path.join(settings.MEDIA_ROOT, rel_path2)
        serve_path = None
        serve_name = None
        if os.path.exists(abs_path1):
            serve_path = abs_path1
            serve_name = f"optimizacion_{folio_actual}_{cliente_slug}.pdf"
        elif os.path.exists(abs_path2):
            serve_path = abs_path2
            serve_name = f"optimizacion_{folio_actual}.pdf"
        if serve_path:
            with open(serve_path, 'rb') as f:
                data = f.read()
            resp = HttpResponse(data, content_type='application/pdf')
            resp['Content-Disposition'] = f'inline; filename="{serve_name}"'
            resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            resp['Pragma'] = 'no-cache'
            return resp

    # Si no existe el PDF del folio actual, regenerar rápido desde el resultado guardado
    try:
        resultado = json.loads(proyecto.resultado_optimizacion) if proyecto.resultado_optimizacion else {}
    except Exception:
        resultado = {}
    pdf_bytes = _pdf_from_result(proyecto, resultado)

    # Guardar como PDF del ID/folio actual (si se pudo obtener)
    rel_dir = f"proyectos/{proyecto.id}"
    if folio_actual:
        try:
            cliente_slug = slugify(proyecto.cliente.nombre) if proyecto.cliente_id else 'cliente'
        except Exception:
            cliente_slug = 'cliente'
        rel_path = f"{rel_dir}/optimizacion_{folio_actual}_{cliente_slug}.pdf"
    else:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        try:
            cliente_slug = slugify(proyecto.cliente.nombre) if proyecto.cliente_id else 'cliente'
        except Exception:
            cliente_slug = 'cliente'
        rel_path = f"{rel_dir}/optimizacion_{proyecto.codigo}_{cliente_slug}_{ts}.pdf"
    abs_dir = os.path.join(settings.MEDIA_ROOT, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)
    abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)
    with open(abs_path, 'wb') as f:
        f.write(pdf_bytes)
    proyecto.archivo_pdf = rel_path
    proyecto.save(update_fields=['archivo_pdf'])

    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = f'inline; filename="{os.path.basename(rel_path)}"'
    resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp['Pragma'] = 'no-cache'
    return resp

 

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def guardar_layout_manual(request):
    """Guarda posiciones/rotaciones manuales de piezas en el resultado del proyecto.
    Espera JSON: { proyecto_id, material_index, updates: [{tablero_num, piezas:[{index,x,y,ancho,largo,rotada}]}] }
    """
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return JsonResponse({'success': False, 'message': 'Payload inválido'}, status=400)

    proyecto_id = payload.get('proyecto_id')
    material_index = int(payload.get('material_index') or 1)
    updates = payload.get('updates') or []
    if not proyecto_id:
        return JsonResponse({'success': False, 'message': 'Falta proyecto_id'}, status=400)

    proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    if not proyecto.resultado_optimizacion:
        return JsonResponse({'success': False, 'message': 'Proyecto sin resultado para actualizar'}, status=400)

    try:
        resultado = json.loads(proyecto.resultado_optimizacion)
    except Exception:
        return JsonResponse({'success': False, 'message': 'Resultado inválido en proyecto'}, status=500)

    materiales = resultado.get('materiales') or [resultado]
    # Resolver material (1-based index del UI)
    mat_idx = max(0, material_index - 1)
    if mat_idx >= len(materiales):
        mat_idx = 0
    mat = materiales[mat_idx]

    tableros = mat.get('tableros') or []
    if not isinstance(tableros, list) or not tableros:
        return JsonResponse({'success': False, 'message': 'No hay tableros para actualizar en el material seleccionado'}, status=400)

    # Aplicar updates por tablero
    for upd in updates:
        try:
            tnum = int(upd.get('tablero_num') or 1)
        except Exception:
            tnum = 1
        t_index = max(0, tnum - 1)
        if t_index >= len(tableros):
            continue
        piezas = tableros[t_index].get('piezas') or []
        for pu in (upd.get('piezas') or []):
            try:
                idx = int(pu.get('index') if pu.get('index') is not None else -1)
            except Exception:
                idx = -1
            if idx < 0 or idx >= len(piezas):
                continue
            p = piezas[idx]
            # Actualizar coordenadas y dimensiones (usar claves del esquema backend)
            try:
                x = float(pu.get('x'))
                y = float(pu.get('y'))
                w = float(pu.get('ancho'))
                l = float(pu.get('largo'))
            except Exception:
                continue
            p['x'] = max(0, round(x, 3))
            p['y'] = max(0, round(y, 3))
            p['ancho'] = max(0, round(w, 3))
            # Normalizamos a 'largo'
            p['largo'] = max(0, round(l, 3))
            # Bandera de rotación
            if 'rotada' in pu:
                p['rotada'] = bool(pu.get('rotada'))

    # Persistir cambios
    if 'materiales' in resultado:
        resultado['materiales'][mat_idx] = mat
    else:
        resultado = mat

    proyecto.resultado_optimizacion = json.dumps(resultado, ensure_ascii=False)
    proyecto.save(update_fields=['resultado_optimizacion'])

    return JsonResponse({'success': True, 'resultado': resultado})

@login_required
def proyectos_optimizador(request):
    """Lista de proyectos de optimización"""
    search = request.GET.get('search', '')
    
    proyectos = Proyecto.objects.filter(usuario=request.user)
    
    if search:
        proyectos = proyectos.filter(
            Q(nombre__icontains=search) |
            Q(descripcion__icontains=search)
        )
    
    proyectos = proyectos.order_by('-fecha_creacion')
    
    paginator = Paginator(proyectos, 20)
    page_number = request.GET.get('page')
    proyectos_page = paginator.get_page(page_number)
    
    context = {
        'proyectos': proyectos_page,
        'search': search,
    }
    return render(request, 'optimizador/proyectos.html', context)


@login_required
@require_http_methods(["POST"])
def forzar_optimizacion(request, proyecto_id:int):
    """Genera y persiste el resultado de optimización desde la configuración del proyecto.
    Útil cuando el proyecto no tiene resultado guardado aún y se quiere exportar PDF o previsualizar.
    """
    proyecto = get_object_or_404(Proyecto, id=proyecto_id)
    # Si ya tiene resultado válido, no recalcular
    try:
        if proyecto.resultado_optimizacion:
            existente = json.loads(proyecto.resultado_optimizacion)
            mats = existente.get('materiales') or [existente]
            if any(len(m.get('tableros') or []) for m in mats):
                return JsonResponse({'success': True, 'message': 'El proyecto ya cuenta con un resultado de optimización.'})
    except Exception:
        pass

    # Intentar construir desde configuración (soporta 1 o varios materiales)
    try:
        if not proyecto.configuracion:
            return JsonResponse({'success': False, 'message': 'El proyecto no tiene configuración guardada para optimizar.'}, status=400)
        cfg = json.loads(proyecto.configuracion) if isinstance(proyecto.configuracion, str) else proyecto.configuracion

        def optimizar_desde(conf_mat, piezas_in):
            material_id = (conf_mat or {}).get('material_id')
            if not (conf_mat and piezas_in and material_id):
                return None
            material = get_object_or_404(Material, id=material_id)
            ancho_tablero = conf_mat.get('ancho_custom') or material.ancho
            largo_tablero = conf_mat.get('largo_custom') or material.largo
            margen_x = conf_mat.get('margen_x', 0)
            margen_y = conf_mat.get('margen_y', 0)
            desperdicio_sierra = conf_mat.get('desperdicio_sierra', 3)
            tapacanto_codigo = conf_mat.get('tapacanto_codigo', '')
            tapacanto_nombre = conf_mat.get('tapacanto_nombre', '')
            engine = OptimizationEngine(ancho_tablero, largo_tablero, margen_x, margen_y, desperdicio_sierra)
            piezas_proc = []
            for p in piezas_in:
                piezas_proc.append({
                    'nombre': p['nombre'],
                    'ancho': p['ancho'],
                    'largo': p['largo'],
                    'cantidad': p.get('cantidad', 1),
                    'veta_libre': p.get('veta_libre', False),
                    'tapacantos': p.get('tapacantos', {}) or {}
                })
            r = engine.optimizar_piezas(piezas_proc)
            r['entrada'] = piezas_proc
            r['material'] = {
                'nombre': material.nombre,
                'codigo': material.codigo,
                'ancho_original': material.ancho,
                'largo_original': material.largo,
                'ancho_usado': ancho_tablero,
                'largo_usado': largo_tablero
            }
            r['config'] = {'margen_x': margen_x, 'margen_y': margen_y, 'kerf': desperdicio_sierra}
            r['tapacanto'] = { 'codigo': tapacanto_codigo, 'nombre': tapacanto_nombre }
            return r

        materiales = []
        if isinstance(cfg, dict) and isinstance(cfg.get('materiales'), list):
            for mcfg in cfg['materiales']:
                conf_mat = mcfg.get('configuracion_material') or mcfg.get('config')
                piezas_in = mcfg.get('piezas') or mcfg.get('entrada')
                r = optimizar_desde(conf_mat, piezas_in)
                if r: materiales.append(r)
        else:
            conf_mat = cfg.get('configuracion_material') or cfg.get('config')
            piezas_in = cfg.get('piezas') or cfg.get('entrada')
            r = optimizar_desde(conf_mat, piezas_in)
            if r: materiales.append(r)

        if not materiales:
            return JsonResponse({'success': False, 'message': 'No hay configuración suficiente (material y piezas) para optimizar.'}, status=400)

        total_tableros = sum(len(m.get('tableros', [])) for m in materiales)
        total_piezas = sum(sum(len(t.get('piezas', [])) for t in m.get('tableros', [])) for m in materiales)
        eficiencias = [m.get('eficiencia') or m.get('eficiencia_promedio') for m in materiales if m]
        eficiencia_promedio = sum(e for e in eficiencias if e) / max(1, len([e for e in eficiencias if e]))
        folio = f"OPT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        resultado_persist = {
            'materiales': materiales,
            'total_tableros': total_tableros,
            'total_piezas': total_piezas,
            'eficiencia_promedio': eficiencia_promedio,
            'ultimo_folio': folio,
            'historial': [{
                'folio': folio,
                'fecha': datetime.now().isoformat(),
                'materiales': materiales,
                'total_tableros': total_tableros,
                'total_piezas': total_piezas,
                'eficiencia_promedio': eficiencia_promedio,
            }]
        }
        proyecto.resultado_optimizacion = json.dumps(resultado_persist, ensure_ascii=False)
        proyecto.total_materiales = len(materiales)
        proyecto.total_tableros = total_tableros
        proyecto.total_piezas = total_piezas
        proyecto.eficiencia_promedio = eficiencia_promedio
        proyecto.estado = 'optimizado'
        proyecto.save()

        return JsonResponse({'success': True, 'message': 'Optimización generada y guardada', 'resumen': {
            'materiales': len(materiales), 'tableros': total_tableros, 'piezas': total_piezas, 'eficiencia': eficiencia_promedio, 'folio': folio
        }})

    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error al optimizar: {str(e)}'}, status=500)

def js_test(request):
    """Vista de prueba para JavaScript"""
    return render(request, 'optimizador/test.html')

def optimizador_clean(request):
    """Vista limpia del optimizador sin complejidades"""
    return render(request, 'optimizador/home-clean.html')

# ====================================================
# ENDPOINTS PARA BÚSQUEDA Y GESTIÓN DE CLIENTES
# ====================================================

@csrf_exempt
def buscar_clientes_ajax(request):
    """Búsqueda en tiempo real de clientes"""
    if request.method == 'GET':
        query = request.GET.get('q', '').strip()
        
        if len(query) < 2:
            return JsonResponse({'clientes': []})
        
        # Buscar clientes por nombre o RUT
        clientes = Cliente.objects.filter(
            activo=True
        ).filter(
            Q(nombre__icontains=query) | Q(rut__icontains=query) | Q(organizacion__nombre__icontains=query)
        ).select_related('organizacion').order_by('nombre')[:10]
        
        resultados = []
        for cliente in clientes:
            resultados.append({
                'id': cliente.id,
                'nombre': cliente.nombre,
                'rut': cliente.rut,
                'organizacion': cliente.organizacion.nombre if cliente.organizacion else '',
                'telefono': cliente.telefono or '',
                'email': cliente.email or ''
            })
        
        return JsonResponse({
            'clientes': resultados,
            'total': len(resultados),
            'query': query
        })
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@csrf_exempt
def crear_cliente_ajax(request):
    """Crear nuevo cliente desde el optimizador"""
    if request.method == 'POST':
        try:
            # Manejar tanto JSON como FormData
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            
            # Validar datos requeridos
            nombre = data.get('nombre', '').strip()
            rut = _normalize_rut(data.get('rut', '') or '')
            
            if not nombre:
                return JsonResponse({'success': False, 'mensaje': 'El nombre es requerido'})
            
            # Si no hay RUT, generar uno temporal basado en el nombre (normalizado)
            if not rut:
                import time
                rut_temporal = f"TEMP-{int(time.time())}"
                rut = _normalize_rut(rut_temporal)

            # Verificar si el RUT ya existe (comparación normalizada)
            if rut and Cliente.objects.filter(rut=rut).exists():
                return JsonResponse({'success': False, 'mensaje': 'Ya existe un cliente con este RUT'})
            
            # Asignar organización del usuario que crea el cliente
            org = None
            try:
                # Intentamos tomar la organización desde el perfil del usuario, si existe
                if hasattr(request.user, 'usuarioperfiloptimizador') and request.user.usuarioperfiloptimizador.organizacion:
                    org = request.user.usuarioperfiloptimizador.organizacion
                elif hasattr(request.user, 'usuario_perfil_optimizador') and request.user.usuario_perfil_optimizador.organizacion:
                    org = request.user.usuario_perfil_optimizador.organizacion
            except Exception:
                org = None

            # Crear nuevo cliente con campos válidos del modelo actual
            cliente = Cliente.objects.create(
                nombre=nombre,
                rut=rut,
                organizacion=org,
                telefono=data.get('telefono', '') or None,
                email=data.get('email', '') or None,
                direccion=data.get('direccion', '') or None,
                activo=True
            )
            # Auditoría: registrar creación de cliente
            try:
                from core.models import AuditLog
                AuditLog.objects.create(
                    actor=request.user if getattr(request, 'user', None) and request.user.is_authenticated else None,
                    organizacion=org,
                    verb='CREATE',
                    target_model='Cliente',
                    target_id=str(cliente.id),
                    target_repr=cliente.nombre,
                    changes=None
                )
            except Exception:
                pass
            
            return JsonResponse({
                'success': True,
                'cliente': {
                    'id': cliente.id,
                    'nombre': cliente.nombre,
                    'rut': cliente.rut,
                    'organizacion': (cliente.organizacion.nombre if getattr(cliente, 'organizacion', None) else ''),
                    'telefono': cliente.telefono or '',
                    'email': cliente.email or ''
                },
                'message': f'Cliente {cliente.nombre} creado exitosamente'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'mensaje': 'Datos JSON inválidos'})
        except Exception as e:
            return JsonResponse({'success': False, 'mensaje': f'Error interno: {str(e)}'})
    
    return JsonResponse({'success': False, 'mensaje': 'Método no permitido'})