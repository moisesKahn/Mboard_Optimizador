/**
 * CUTTING OPTIMIZER - Algoritmo Avanzado de Optimización de Cortes
 * ==============================================================
 * 
 * Este módulo implementa algoritmos avanzados para la optimización de cortes
 * de tableros, incluyendo múltiples estrategias y técnicas heurísticas.
 * 
 * Algoritmos implementados:
 * - Bottom Left Fill (BLF) mejorado
 * - Best Fit Decreasing Height (BFDH)
 * - Guillotine Algorithm
 * - Genetic Algorithm básico
 * 
 * @author AI Assistant
 * @version 2.0
 * @date 2025-10-14
 */

class CuttingOptimizer {
    constructor() {
        this.debugMode = true;
        this.algoritmos = {
            BLF: 'Bottom Left Fill',
            BFDH: 'Best Fit Decreasing Height', 
            GUILLOTINE: 'Guillotine Algorithm',
            GENETIC: 'Genetic Algorithm',
            HYBRID: 'Hybrid Multi-Strategy'
        };
    }

    /**
     * Punto de entrada principal para la optimización
     */
    optimize(piezas, tableroConfig, opciones = {}) {
        const config = {
            algoritmo: opciones.algoritmo || 'HYBRID',
            maxTableros: opciones.maxTableros || 50,
            permitirRotacion: opciones.permitirRotacion !== false,
            margenError: opciones.margenError || 0.1,
            ...opciones
        };

        this.log('=== INICIANDO OPTIMIZACIÓN AVANZADA ===');
        this.log(`Algoritmo: ${this.algoritmos[config.algoritmo]}`);
        this.log(`Piezas: ${piezas.length}`);
        this.log(`Tablero: ${tableroConfig.ancho}x${tableroConfig.alto}mm`);

        const piezasExpandidas = this.expandirPiezas(piezas);
        
        let resultado;
        switch (config.algoritmo) {
            case 'BLF':
                resultado = this.optimizarBLF(piezasExpandidas, tableroConfig, config);
                break;
            case 'BFDH':
                resultado = this.optimizarBFDH(piezasExpandidas, tableroConfig, config);
                break;
            case 'GUILLOTINE':
                resultado = this.optimizarGuillotine(piezasExpandidas, tableroConfig, config);
                break;
            case 'GENETIC':
                resultado = this.optimizarGenetic(piezasExpandidas, tableroConfig, config);
                break;
            case 'HYBRID':
            default:
                resultado = this.optimizarHybrid(piezasExpandidas, tableroConfig, config);
                break;
        }

        this.log('=== OPTIMIZACIÓN COMPLETADA ===');
        return resultado;
    }

    /**
     * Algoritmo Híbrido - Combina múltiples estrategias
     */
    optimizarHybrid(piezas, tableroConfig, config) {
        const estrategias = [
            () => this.optimizarBLF(piezas, tableroConfig, config),
            () => this.optimizarBFDH(piezas, tableroConfig, config),
            () => this.optimizarGuillotine(piezas, tableroConfig, config)
        ];

        let mejorResultado = null;
        let mejorScore = -1;

        this.log('Probando múltiples algoritmos...');

        estrategias.forEach((estrategia, index) => {
            try {
                const resultado = estrategia();
                const score = this.evaluarResultado(resultado);
                
                this.log(`Estrategia ${index + 1}: ${resultado.tableros.length} tableros, Score: ${score.toFixed(2)}`);
                
                if (score > mejorScore) {
                    mejorScore = score;
                    mejorResultado = resultado;
                    mejorResultado.algoritmoUsado = ['BLF', 'BFDH', 'GUILLOTINE'][index];
                }
            } catch (error) {
                this.log(`Error en estrategia ${index + 1}: ${error.message}`);
            }
        });

        if (!mejorResultado) {
            throw new Error('Ninguna estrategia pudo optimizar las piezas');
        }

        mejorResultado.score = mejorScore;
        return mejorResultado;
    }

    /**
     * Bottom Left Fill mejorado con análisis de huecos
     */
    optimizarBLF(piezas, tableroConfig, config) {
        this.log('Ejecutando Bottom Left Fill mejorado...');
        
        const tableros = [];
        const piezasOrdenadas = this.ordenarPiezasPorArea(piezas, true);
        
        for (const pieza of piezasOrdenadas) {
            let colocada = false;
            
            // Intentar en tableros existentes
            for (const tablero of tableros) {
                if (this.colocarPiezaBLF(pieza, tablero, config)) {
                    colocada = true;
                    break;
                }
            }
            
            // Crear nuevo tablero si es necesario
            if (!colocada) {
                const nuevoTablero = new TableroOptimizado(tableroConfig);
                nuevoTablero.id = tableros.length + 1;
                
                if (this.colocarPiezaBLF(pieza, nuevoTablero, config)) {
                    tableros.push(nuevoTablero);
                    colocada = true;
                }
            }
            
            if (!colocada) {
                this.log(`⚠️ No se pudo colocar: ${pieza.nombre} (${pieza.ancho}x${pieza.alto})`);
            }
        }
        
        return {
            tableros,
            piezasNoColocadas: piezasOrdenadas.filter(p => !p.colocada),
            algoritmo: 'BLF',
            stats: this.calcularEstadisticas(tableros)
        };
    }

    /**
     * Best Fit Decreasing Height
     */
    optimizarBFDH(piezas, tableroConfig, config) {
        this.log('Ejecutando Best Fit Decreasing Height...');
        
        const tableros = [];
        const piezasOrdenadas = piezas.slice().sort((a, b) => b.alto - a.alto);
        
        for (const pieza of piezasOrdenadas) {
            let mejorTablero = null;
            let mejorScore = -1;
            
            // Buscar el mejor tablero existente
            for (const tablero of tableros) {
                const score = this.evaluarAjusteBFDH(pieza, tablero);
                if (score > mejorScore) {
                    mejorScore = score;
                    mejorTablero = tablero;
                }
            }
            
            let colocada = false;
            if (mejorTablero && mejorScore > 0) {
                colocada = this.colocarPiezaBFDH(pieza, mejorTablero, config);
            }
            
            // Crear nuevo tablero si es necesario
            if (!colocada) {
                const nuevoTablero = new TableroOptimizado(tableroConfig);
                nuevoTablero.id = tableros.length + 1;
                
                if (this.colocarPiezaBFDH(pieza, nuevoTablero, config)) {
                    tableros.push(nuevoTablero);
                    colocada = true;
                }
            }
            
            if (!colocada) {
                this.log(`⚠️ No se pudo colocar: ${pieza.nombre} (${pieza.ancho}x${pieza.alto})`);
            }
        }
        
        return {
            tableros,
            piezasNoColocadas: piezasOrdenadas.filter(p => !p.colocada),
            algoritmo: 'BFDH',
            stats: this.calcularEstadisticas(tableros)
        };
    }

    /**
     * Algoritmo Guillotina - Optimizado para cortes rectos
     */
    optimizarGuillotine(piezas, tableroConfig, config) {
        this.log('Ejecutando Algoritmo Guillotina...');
        
        const tableros = [];
        const piezasOrdenadas = this.ordenarPiezasPorArea(piezas, true);
        
        for (const pieza of piezasOrdenadas) {
            let colocada = false;
            
            // Intentar en tableros existentes
            for (const tablero of tableros) {
                if (this.colocarPiezaGuillotine(pieza, tablero, config)) {
                    colocada = true;
                    break;
                }
            }
            
            // Crear nuevo tablero si es necesario
            if (!colocada) {
                const nuevoTablero = new TableroGuillotina(tableroConfig);
                nuevoTablero.id = tableros.length + 1;
                
                if (this.colocarPiezaGuillotine(pieza, nuevoTablero, config)) {
                    tableros.push(nuevoTablero);
                    colocada = true;
                }
            }
            
            if (!colocada) {
                this.log(`⚠️ No se pudo colocar: ${pieza.nombre} (${pieza.ancho}x${pieza.alto})`);
            }
        }
        
        return {
            tableros,
            piezasNoColocadas: piezasOrdenadas.filter(p => !p.colocada),
            algoritmo: 'GUILLOTINE',
            stats: this.calcularEstadisticas(tableros)
        };
    }

    /**
     * Algoritmo Genético básico
     */
    optimizarGenetic(piezas, tableroConfig, config) {
        this.log('Ejecutando Algoritmo Genético...');
        
        const parametros = {
            poblacion: 20,
            generaciones: 50,
            mutacion: 0.1,
            elite: 0.2
        };
        
        // Generar población inicial
        let poblacion = [];
        for (let i = 0; i < parametros.poblacion; i++) {
            const orden = this.generarOrdenAleatorio(piezas);
            const resultado = this.optimizarBLF(orden, tableroConfig, config);
            poblacion.push({
                orden,
                resultado,
                fitness: this.evaluarResultado(resultado)
            });
        }
        
        // Evolucionar
        for (let gen = 0; gen < parametros.generaciones; gen++) {
            // Selección y reproducción
            poblacion.sort((a, b) => b.fitness - a.fitness);
            
            const nuevaPoblacion = [];
            const elite = Math.floor(parametros.poblacion * parametros.elite);
            
            // Mantener elite
            for (let i = 0; i < elite; i++) {
                nuevaPoblacion.push(poblacion[i]);
            }
            
            // Generar nueva descendencia
            while (nuevaPoblacion.length < parametros.poblacion) {
                const padre1 = this.seleccionarPadre(poblacion);
                const padre2 = this.seleccionarPadre(poblacion);
                const hijo = this.cruzar(padre1.orden, padre2.orden);
                
                if (Math.random() < parametros.mutacion) {
                    this.mutar(hijo);
                }
                
                const resultado = this.optimizarBLF(hijo, tableroConfig, config);
                nuevaPoblacion.push({
                    orden: hijo,
                    resultado,
                    fitness: this.evaluarResultado(resultado)
                });
            }
            
            poblacion = nuevaPoblacion;
            
            if (gen % 10 === 0) {
                this.log(`Generación ${gen}: Mejor fitness = ${poblacion[0].fitness.toFixed(2)}`);
            }
        }
        
        poblacion.sort((a, b) => b.fitness - a.fitness);
        const mejorSolucion = poblacion[0].resultado;
        mejorSolucion.algoritmo = 'GENETIC';
        
        return mejorSolucion;
    }

    /**
     * Colocar pieza usando Bottom Left Fill
     */
    colocarPiezaBLF(pieza, tablero, config) {
        const orientaciones = config.permitirRotacion && pieza.puedeRotar() ? [false, true] : [false];
        
        for (const rotar of orientaciones) {
            if (rotar) pieza.rotar();
            
            const posicion = this.encontrarPosicionBLF(pieza, tablero);
            if (posicion && tablero.puedeColocar(pieza, posicion.x, posicion.y)) {
                pieza.x = posicion.x;
                pieza.y = posicion.y;
                pieza.colocada = true;
                pieza.rotada = rotar;
                tablero.colocarPieza(pieza);
                
                this.log(`✓ BLF: ${pieza.nombre} colocada en (${posicion.x}, ${posicion.y})`);
                return true;
            }
            
            if (rotar) pieza.rotar(); // Restaurar orientación
        }
        
        return false;
    }

    /**
     * Encontrar posición Bottom Left Fill optimizada
     */
    encontrarPosicionBLF(pieza, tablero) {
        let mejorPosicion = null;
        let menorY = tablero.altoUtil;
        let menorX = tablero.anchoUtil;
        let mejorScore = -1;
        
        const paso = Math.max(1, tablero.kerf);
        
        for (let y = 0; y <= tablero.altoUtil - pieza.alto; y += paso) {
            for (let x = 0; x <= tablero.anchoUtil - pieza.ancho; x += paso) {
                if (tablero.puedeColocar(pieza, x, y)) {
                    // Calcular score de posición (priorizar esquina inferior izquierda)
                    const score = this.calcularScorePosicion(x, y, pieza, tablero);
                    
                    if (y < menorY || (y === menorY && x < menorX) || 
                        (y === menorY && x === menorX && score > mejorScore)) {
                        mejorPosicion = { x, y };
                        menorY = y;
                        menorX = x;
                        mejorScore = score;
                    }
                }
            }
        }
        
        return mejorPosicion;
    }

    /**
     * Calcular score de una posición (considera desperdicio y adyacencia)
     */
    calcularScorePosicion(x, y, pieza, tablero) {
        let score = 0;
        
        // Bonus por estar en esquina inferior izquierda
        score += (tablero.anchoUtil - x) * 0.1;
        score += (tablero.altoUtil - y) * 0.1;
        
        // Bonus por adyacencia con otras piezas
        const adyacencias = tablero.contarAdyacencias(x, y, pieza.ancho, pieza.alto);
        score += adyacencias * 10;
        
        // Penalty por crear huecos pequeños
        const huecosCreados = tablero.evaluarHuecosCreados(x, y, pieza.ancho, pieza.alto);
        score -= huecosCreados * 5;
        
        return score;
    }

    /**
     * Colocar pieza usando BFDH
     */
    colocarPiezaBFDH(pieza, tablero, config) {
        const orientaciones = config.permitirRotacion && pieza.puedeRotar() ? [false, true] : [false];
        
        for (const rotar of orientaciones) {
            if (rotar) pieza.rotar();
            
            const nivel = this.encontrarMejorNivel(pieza, tablero);
            if (nivel) {
                pieza.x = nivel.x;
                pieza.y = nivel.y;
                pieza.colocada = true;
                pieza.rotada = rotar;
                tablero.colocarPieza(pieza);
                tablero.actualizarNiveles(nivel);
                
                this.log(`✓ BFDH: ${pieza.nombre} colocada en nivel (${nivel.x}, ${nivel.y})`);
                return true;
            }
            
            if (rotar) pieza.rotar(); // Restaurar orientación
        }
        
        return false;
    }

    /**
     * Expandir piezas según cantidad
     */
    expandirPiezas(piezas) {
        const expandidas = [];
        
        piezas.forEach((pieza, index) => {
            for (let i = 0; i < pieza.cantidad; i++) {
                const piezaExpandida = new PiezaOptimizada({
                    nombre: `${pieza.nombre}_${i + 1}`,
                    ancho: pieza.ancho,
                    alto: pieza.alto,
                    descripcion: pieza.descripcion,
                    puedeRotar: pieza.puedeRotar !== false,
                    material: pieza.material,
                    espesor: pieza.espesor || 18
                });
                
                piezaExpandida.indiceOriginal = index;
                expandidas.push(piezaExpandida);
            }
        });
        
        this.log(`Piezas expandidas: ${expandidas.length} de ${piezas.length} tipos`);
        return expandidas;
    }

    /**
     * Ordenar piezas por diferentes criterios
     */
    ordenarPiezasPorArea(piezas, descendente = true) {
        return piezas.slice().sort((a, b) => {
            const areaA = a.ancho * a.alto;
            const areaB = b.ancho * b.alto;
            return descendente ? areaB - areaA : areaA - areaB;
        });
    }

    /**
     * Evaluar resultado de optimización
     */
    evaluarResultado(resultado) {
        if (!resultado || !resultado.tableros || resultado.tableros.length === 0) {
            return 0;
        }
        
        let score = 0;
        let areaTotal = 0;
        let areaUsada = 0;
        
        resultado.tableros.forEach(tablero => {
            const aprovechamiento = tablero.getAprovechamiento();
            areaTotal += tablero.getAreaTotal();
            areaUsada += tablero.getAreaUsada();
            
            // Score basado en aprovechamiento y número de tableros
            score += aprovechamiento * 100;
        });
        
        // Penalty por número de tableros
        score -= resultado.tableros.length * 5;
        
        // Bonus por aprovechamiento global
        const aprovechamientoGlobal = areaTotal > 0 ? (areaUsada / areaTotal) * 100 : 0;
        score += aprovechamientoGlobal;
        
        return Math.max(0, score);
    }

    /**
     * Calcular estadísticas del resultado
     */
    calcularEstadisticas(tableros) {
        let areaTotal = 0;
        let areaUsada = 0;
        let piezasColocadas = 0;
        
        tableros.forEach(tablero => {
            areaTotal += tablero.getAreaTotal();
            areaUsada += tablero.getAreaUsada();
            piezasColocadas += tablero.piezas.length;
        });
        
        return {
            numeroTableros: tableros.length,
            areaTotal: areaTotal,
            areaUsada: areaUsada,
            aprovechamientoGlobal: areaTotal > 0 ? (areaUsada / areaTotal) * 100 : 0,
            piezasColocadas: piezasColocadas,
            desperdicioTotal: areaTotal - areaUsada
        };
    }

    /**
     * Generar orden aleatorio para algoritmo genético
     */
    generarOrdenAleatorio(piezas) {
        const orden = piezas.slice();
        for (let i = orden.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [orden[i], orden[j]] = [orden[j], orden[i]];
        }
        return orden;
    }

    /**
     * Logging con control de depuración
     */
    log(mensaje) {
        if (this.debugMode) {
            console.log(`[CuttingOptimizer] ${mensaje}`);
        }
    }
}

/**
 * Clase optimizada para representar tableros
 */
class TableroOptimizado {
    constructor(config) {
        this.ancho = config.ancho;
        this.alto = config.alto;
        this.margen = config.margen || 10;
        this.kerf = config.kerf || 3;
        
        this.anchoUtil = this.ancho - (2 * this.margen);
        this.altoUtil = this.alto - (2 * this.margen);
        
        this.piezas = [];
        this.huecos = []; // Espacios libres
        this.id = 0;
        
        // Inicializar con un hueco del tamaño completo
        this.huecos.push({
            x: 0,
            y: 0,
            ancho: this.anchoUtil,
            alto: this.altoUtil,
            libre: true
        });
    }

    puedeColocar(pieza, x, y) {
        // Verificar límites
        if (x < 0 || y < 0 || 
            x + pieza.ancho > this.anchoUtil || 
            y + pieza.alto > this.altoUtil) {
            return false;
        }
        
        // Verificar colisiones con piezas existentes
        for (const otraPieza of this.piezas) {
            if (this.hayColision(pieza, x, y, otraPieza)) {
                return false;
            }
        }
        
        return true;
    }

    hayColision(pieza, x, y, otraPieza) {
        const margenKerf = this.kerf;
        
        const x1 = x - margenKerf;
        const y1 = y - margenKerf;
        const x1_fin = x + pieza.ancho + margenKerf;
        const y1_fin = y + pieza.alto + margenKerf;
        
        const x2_inicio = otraPieza.x - margenKerf;
        const y2_inicio = otraPieza.y - margenKerf;
        const x2_fin = otraPieza.x + otraPieza.ancho + margenKerf;
        const y2_fin = otraPieza.y + otraPieza.alto + margenKerf;
        
        return !(x1_fin <= x2_inicio || x2_fin <= x1 || y1_fin <= y2_inicio || y2_fin <= y1);
    }

    colocarPieza(pieza) {
        this.piezas.push(pieza);
        this.actualizarHuecos(pieza);
    }

    actualizarHuecos(pieza) {
        // Algoritmo para mantener actualizada la lista de huecos libres
        const nuevosHuecos = [];
        
        for (const hueco of this.huecos) {
            if (hueco.libre && this.huecoSeSuperpone(hueco, pieza)) {
                // Dividir hueco en partes no ocupadas
                const fragmentos = this.dividirHueco(hueco, pieza);
                nuevosHuecos.push(...fragmentos);
            } else {
                nuevosHuecos.push(hueco);
            }
        }
        
        this.huecos = nuevosHuecos;
        this.optimizarHuecos();
    }

    huecoSeSuperpone(hueco, pieza) {
        return !(pieza.x >= hueco.x + hueco.ancho ||
                 pieza.x + pieza.ancho <= hueco.x ||
                 pieza.y >= hueco.y + hueco.alto ||
                 pieza.y + pieza.alto <= hueco.y);
    }

    dividirHueco(hueco, pieza) {
        const fragmentos = [];
        
        // Fragmento izquierdo
        if (pieza.x > hueco.x) {
            fragmentos.push({
                x: hueco.x,
                y: hueco.y,
                ancho: pieza.x - hueco.x,
                alto: hueco.alto,
                libre: true
            });
        }
        
        // Fragmento derecho
        if (pieza.x + pieza.ancho < hueco.x + hueco.ancho) {
            fragmentos.push({
                x: pieza.x + pieza.ancho,
                y: hueco.y,
                ancho: hueco.x + hueco.ancho - (pieza.x + pieza.ancho),
                alto: hueco.alto,
                libre: true
            });
        }
        
        // Fragmento superior
        if (pieza.y > hueco.y) {
            fragmentos.push({
                x: hueco.x,
                y: hueco.y,
                ancho: hueco.ancho,
                alto: pieza.y - hueco.y,
                libre: true
            });
        }
        
        // Fragmento inferior
        if (pieza.y + pieza.alto < hueco.y + hueco.alto) {
            fragmentos.push({
                x: hueco.x,
                y: pieza.y + pieza.alto,
                ancho: hueco.ancho,
                alto: hueco.y + hueco.alto - (pieza.y + pieza.alto),
                libre: true
            });
        }
        
        return fragmentos.filter(f => f.ancho > 0 && f.alto > 0);
    }

    optimizarHuecos() {
        // Fusionar huecos adyacentes para optimizar el espacio
        // Implementación simplificada
        this.huecos = this.huecos.filter(h => h.ancho > 1 && h.alto > 1);
    }

    contarAdyacencias(x, y, ancho, alto) {
        let contador = 0;
        
        for (const pieza of this.piezas) {
            // Verificar adyacencia en los bordes
            if ((pieza.x + pieza.ancho === x && this.rangosSeSolapan(pieza.y, pieza.y + pieza.alto, y, y + alto)) ||
                (x + ancho === pieza.x && this.rangosSeSolapan(pieza.y, pieza.y + pieza.alto, y, y + alto)) ||
                (pieza.y + pieza.alto === y && this.rangosSeSolapan(pieza.x, pieza.x + pieza.ancho, x, x + ancho)) ||
                (y + alto === pieza.y && this.rangosSeSolapan(pieza.x, pieza.x + pieza.ancho, x, x + ancho))) {
                contador++;
            }
        }
        
        return contador;
    }

    rangosSeSolapan(a1, a2, b1, b2) {
        return Math.max(a1, b1) < Math.min(a2, b2);
    }

    evaluarHuecosCreados(x, y, ancho, alto) {
        // Evalúa cuántos huecos pequeños se crearían
        let huecosPequenos = 0;
        const umbralPequeno = 100 * 100; // 100mm x 100mm
        
        for (const hueco of this.huecos) {
            if (this.huecoSeSuperpone({x, y, ancho, alto}, {x: hueco.x, y: hueco.y, ancho: hueco.ancho, alto: hueco.alto})) {
                if (hueco.ancho * hueco.alto < umbralPequeno) {
                    huecosPequenos++;
                }
            }
        }
        
        return huecosPequenos;
    }

    getAreaTotal() {
        return this.anchoUtil * this.altoUtil;
    }

    getAreaUsada() {
        return this.piezas.reduce((sum, pieza) => sum + (pieza.ancho * pieza.alto), 0);
    }

    getAprovechamiento() {
        const areaTotal = this.getAreaTotal();
        return areaTotal > 0 ? (this.getAreaUsada() / areaTotal) * 100 : 0;
    }
}

/**
 * Clase optimizada para representar piezas
 */
class PiezaOptimizada {
    constructor(config) {
        this.nombre = config.nombre;
        this.ancho = config.ancho;
        this.alto = config.alto;
        this.descripcion = config.descripcion || '';
        this.puedeRotarFlag = config.puedeRotar !== false;
        this.material = config.material || '';
        this.espesor = config.espesor || 18;
        
        // Estado
        this.x = 0;
        this.y = 0;
        this.colocada = false;
        this.rotada = false;
        this.indiceOriginal = -1;
    }

    puedeRotar() {
        return this.puedeRotarFlag && this.ancho !== this.alto;
    }

    rotar() {
        if (this.puedeRotar()) {
            [this.ancho, this.alto] = [this.alto, this.ancho];
            return true;
        }
        return false;
    }

    getArea() {
        return this.ancho * this.alto;
    }

    getPerimetro() {
        return 2 * (this.ancho + this.alto);
    }

    clone() {
        const clon = new PiezaOptimizada({
            nombre: this.nombre,
            ancho: this.ancho,
            alto: this.alto,
            descripcion: this.descripcion,
            puedeRotar: this.puedeRotarFlag,
            material: this.material,
            espesor: this.espesor
        });
        
        clon.x = this.x;
        clon.y = this.y;
        clon.colocada = this.colocada;
        clon.rotada = this.rotada;
        clon.indiceOriginal = this.indiceOriginal;
        
        return clon;
    }
}

/**
 * Especialización para algoritmo Guillotina
 */
class TableroGuillotina extends TableroOptimizado {
    constructor(config) {
        super(config);
        this.cortes = []; // Historial de cortes
        this.rectangulos = [{
            x: 0,
            y: 0,
            ancho: this.anchoUtil,
            alto: this.altoUtil,
            libre: true
        }];
    }

    colocarPiezaGuillotine(pieza) {
        // Buscar el mejor rectángulo libre
        let mejorRect = null;
        let mejorScore = -1;
        
        for (const rect of this.rectangulos) {
            if (rect.libre && rect.ancho >= pieza.ancho && rect.alto >= pieza.alto) {
                const score = this.evaluarRectanguloGuillotine(rect, pieza);
                if (score > mejorScore) {
                    mejorScore = score;
                    mejorRect = rect;
                }
            }
        }
        
        if (mejorRect) {
            // Colocar pieza
            pieza.x = mejorRect.x;
            pieza.y = mejorRect.y;
            pieza.colocada = true;
            this.piezas.push(pieza);
            
            // Dividir rectángulo según corte guillotina
            this.dividirRectanguloGuillotine(mejorRect, pieza);
            
            return true;
        }
        
        return false;
    }

    evaluarRectanguloGuillotine(rect, pieza) {
        // Preferir ajuste exacto o mínimo desperdicio
        const desperdicioAncho = rect.ancho - pieza.ancho;
        const desperdicioAlto = rect.alto - pieza.alto;
        const desperdicioTotal = desperdicioAncho * rect.alto + desperdicioAlto * pieza.ancho;
        
        return 1000 - desperdicioTotal; // Score más alto = menos desperdicio
    }

    dividirRectanguloGuillotine(rect, pieza) {
        // Marcar rectángulo como ocupado
        rect.libre = false;
        
        // Decidir dirección de corte (horizontal vs vertical)
        const sobraAncho = rect.ancho - pieza.ancho;
        const sobraAlto = rect.alto - pieza.alto;
        
        if (sobraAncho > 0 && sobraAlto > 0) {
            // Crear dos nuevos rectángulos
            if (sobraAncho >= sobraAlto) {
                // Corte vertical
                this.rectangulos.push({
                    x: rect.x + pieza.ancho,
                    y: rect.y,
                    ancho: sobraAncho,
                    alto: rect.alto,
                    libre: true
                });
                
                this.rectangulos.push({
                    x: rect.x,
                    y: rect.y + pieza.alto,
                    ancho: pieza.ancho,
                    alto: sobraAlto,
                    libre: true
                });
            } else {
                // Corte horizontal
                this.rectangulos.push({
                    x: rect.x,
                    y: rect.y + pieza.alto,
                    ancho: rect.ancho,
                    alto: sobraAlto,
                    libre: true
                });
                
                this.rectangulos.push({
                    x: rect.x + pieza.ancho,
                    y: rect.y,
                    ancho: sobraAncho,
                    alto: pieza.alto,
                    libre: true
                });
            }
        } else if (sobraAncho > 0) {
            // Solo sobra ancho
            this.rectangulos.push({
                x: rect.x + pieza.ancho,
                y: rect.y,
                ancho: sobraAncho,
                alto: rect.alto,
                libre: true
            });
        } else if (sobraAlto > 0) {
            // Solo sobra alto
            this.rectangulos.push({
                x: rect.x,
                y: rect.y + pieza.alto,
                ancho: rect.ancho,
                alto: sobraAlto,
                libre: true
            });
        }
        
        // Registrar corte
        this.cortes.push({
            tipo: sobraAncho >= sobraAlto ? 'vertical' : 'horizontal',
            x: rect.x,
            y: rect.y,
            pieza: pieza.nombre
        });
    }
}

// Exportar para uso global
if (typeof window !== 'undefined') {
    window.CuttingOptimizer = CuttingOptimizer;
    window.TableroOptimizado = TableroOptimizado;
    window.PiezaOptimizada = PiezaOptimizada;
    window.TableroGuillotina = TableroGuillotina;
}

// Exportar para Node.js si está disponible
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        CuttingOptimizer,
        TableroOptimizado,
        PiezaOptimizada,
        TableroGuillotina
    };
}