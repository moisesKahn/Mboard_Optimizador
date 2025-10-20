// ====================================================
// OPTIMIZADOR - JavaScript Simplificado y Funcional
// ====================================================

console.log('🚀 Optimizador JS Simple - Cargando...');

// Variables globales
let clientesData = [];
let materialActual = 1;

// ====================================================
// FUNCIONES BÁSICAS DE PRUEBA
// ====================================================

function probarConectividad() {
    alert('✅ JavaScript funciona perfectamente!');
    console.log('✅ Test de conectividad exitoso');
}

function probarCheckbox() {
    console.log('🧪 Probando checkbox...');
    const checkbox = document.getElementById('permitirEdicionCheck');
    if (checkbox) {
        checkbox.checked = !checkbox.checked;
        toggleMedidasEditables();
    } else {
        alert('❌ Checkbox no encontrado');
    }
}

// ====================================================
// FUNCIÓN TOGGLE MEDIDAS (SIMPLIFICADA)
// ====================================================

function toggleMedidasEditables() {
    console.log('🔧 Toggle medidas - inicio');
    
    const anchoTablero = document.getElementById('anchoTablero');
    const largoTablero = document.getElementById('largoTablero');
    const checkbox = document.getElementById('permitirEdicionCheck');
    
    if (!anchoTablero || !largoTablero || !checkbox) {
        console.error('❌ Elementos no encontrados');
        return;
    }
    
    if (checkbox.checked) {
        // Habilitar
        anchoTablero.readOnly = false;
        largoTablero.readOnly = false;
        anchoTablero.style.backgroundColor = '#fff3cd';
        largoTablero.style.backgroundColor = '#fff3cd';
        console.log('✅ Medidas habilitadas');
        
        // Cambiar texto del label
        const texto = document.getElementById('estadoEdicionTexto');
        if (texto) texto.textContent = 'Habilitado';
    } else {
        // Deshabilitar
        anchoTablero.readOnly = true;
        largoTablero.readOnly = true;
        anchoTablero.style.backgroundColor = '';
        largoTablero.style.backgroundColor = '';
        console.log('🔒 Medidas bloqueadas');
        
        // Cambiar texto del label
        const texto = document.getElementById('estadoEdicionTexto');
        if (texto) texto.textContent = 'Bloqueado';
    }
}

// ====================================================
// FUNCIÓN AGREGAR PIEZA (SIMPLIFICADA)
// ====================================================

function agregarPieza() {
    console.log('➕ Agregando nueva pieza...');
    
    const tbody = document.getElementById('piezasTableBody');
    if (!tbody) {
        console.error('❌ Tabla de piezas no encontrada');
        return;
    }
    
    const numeroNuevaPieza = tbody.children.length + 1;
    
    const nuevaFila = document.createElement('tr');
    nuevaFila.id = `pieza_${numeroNuevaPieza}`;
    nuevaFila.innerHTML = `
        <td class="text-center">${numeroNuevaPieza}</td>
        <td><input type="number" class="form-control form-control-sm" value="1" min="1" style="width: 85px;"></td>
        <td><input type="text" class="form-control form-control-sm" placeholder="Nombre pieza"></td>
        <td><input type="number" class="form-control form-control-sm" placeholder="0" min="1" style="width: 115px;"></td>
        <td><input type="number" class="form-control form-control-sm" placeholder="0" min="1" style="width: 115px;"></td>
        <td class="text-center">
            <input type="checkbox" class="form-check-input" checked>
        </td>
        <td>
            <div class="tapacanto-buttons">
                <button type="button" class="btn btn-outline-secondary btn-xs">⬛</button>
                <button type="button" class="btn btn-outline-secondary btn-xs">⬇️</button>
                <button type="button" class="btn btn-outline-secondary btn-xs">➡️</button>
                <button type="button" class="btn btn-outline-secondary btn-xs">⬆️</button>
                <button type="button" class="btn btn-outline-secondary btn-xs">⬅️</button>
            </div>
        </td>
        <td class="text-center">
            <button type="button" class="btn btn-sm btn-danger" onclick="eliminarPieza(${numeroNuevaPieza})">
                <i class="fas fa-trash"></i>
            </button>
        </td>
    `;
    
    tbody.appendChild(nuevaFila);
    console.log('✅ Pieza agregada:', numeroNuevaPieza);
}

// ====================================================
// FUNCIÓN CARGAR EJEMPLO (SIMPLIFICADA)
// ====================================================

function cargarEjemplo() {
    console.log('📋 Cargando ejemplo...');
    
    // Cargar cliente ejemplo
    const clienteInput = document.getElementById('clienteInput');
    if (clienteInput) {
        clienteInput.value = 'Cliente Ejemplo';
    }
    
    // Cargar RUT ejemplo
    const rutInput = document.getElementById('rutCliente');
    if (rutInput) {
        rutInput.value = '12.345.678-9';
    }
    
    // Limpiar tabla y agregar piezas ejemplo
    const tbody = document.getElementById('piezasTableBody');
    if (tbody) {
        tbody.innerHTML = '';
        
        // Agregar 3 piezas ejemplo
        for (let i = 1; i <= 3; i++) {
            agregarPieza();
        }
        
        // Llenar datos ejemplo
        setTimeout(() => {
            const filas = tbody.querySelectorAll('tr');
            if (filas[0]) {
                filas[0].querySelector('td:nth-child(3) input').value = 'Puerta Principal';
                filas[0].querySelector('td:nth-child(4) input').value = '2000';
                filas[0].querySelector('td:nth-child(5) input').value = '800';
            }
            if (filas[1]) {
                filas[1].querySelector('td:nth-child(3) input').value = 'Estante Superior';
                filas[1].querySelector('td:nth-child(4) input').value = '600';
                filas[1].querySelector('td:nth-child(5) input').value = '300';
            }
            if (filas[2]) {
                filas[2].querySelector('td:nth-child(3) input').value = 'Estante Inferior';
                filas[2].querySelector('td:nth-child(4) input').value = '600';
                filas[2].querySelector('td:nth-child(5) input').value = '300';
            }
        }, 100);
    }
    
    console.log('✅ Ejemplo cargado');
}

// ====================================================
// FUNCIÓN BUSCAR CLIENTES (SIMPLIFICADA)
// ====================================================

function buscarClientes(valor) {
    console.log('🔍 Buscando clientes:', valor);
    
    if (!valor || valor.length < 2) {
        const sugerencias = document.getElementById('clientesSugerencias');
        if (sugerencias) {
            sugerencias.classList.add('d-none');
        }
        return;
    }
    
    // Simular búsqueda con datos básicos
    const resultados = [
        { id: 1, nombre: 'Cliente Ejemplo 1', rut: '11.111.111-1' },
        { id: 2, nombre: 'Cliente Ejemplo 2', rut: '22.222.222-2' },
        { id: 3, nombre: 'Cliente Ejemplo 3', rut: '33.333.333-3' }
    ].filter(cliente => 
        cliente.nombre.toLowerCase().includes(valor.toLowerCase())
    );
    
    mostrarSugerenciasClientes(resultados);
}

function mostrarSugerenciasClientes(clientes) {
    const sugerencias = document.getElementById('clientesSugerencias');
    if (!sugerencias) return;
    
    if (clientes.length === 0) {
        sugerencias.classList.add('d-none');
        return;
    }
    
    sugerencias.innerHTML = clientes.map(cliente => `
        <div class="p-2 border-bottom cursor-pointer hover-bg-light" onclick="seleccionarClienteSugerido('${cliente.nombre}', '${cliente.rut}')">
            <strong>${cliente.nombre}</strong><br>
            <small class="text-muted">${cliente.rut}</small>
        </div>
    `).join('');
    
    sugerencias.classList.remove('d-none');
}

function seleccionarClienteSugerido(nombre, rut) {
    const clienteInput = document.getElementById('clienteInput');
    const rutInput = document.getElementById('rutCliente');
    const sugerencias = document.getElementById('clientesSugerencias');
    
    if (clienteInput) clienteInput.value = nombre;
    if (rutInput) rutInput.value = rut;
    if (sugerencias) sugerencias.classList.add('d-none');
    
    console.log('✅ Cliente seleccionado:', nombre);
}

// ====================================================
// INICIALIZACIÓN
// ====================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 DOM cargado - Inicializando optimizador...');
    
    // Verificar elementos básicos
    setTimeout(() => {
        console.log('📋 Verificación de elementos:');
        console.log('- Cliente input:', !!document.getElementById('clienteInput'));
        console.log('- Ancho tablero:', !!document.getElementById('anchoTablero'));
        console.log('- Tabla piezas:', !!document.getElementById('piezasTableBody'));
        console.log('- Checkbox edición:', !!document.getElementById('permitirEdicionCheck'));
        
        console.log('✅ Optimizador inicializado correctamente');
    }, 500);
});

console.log('✅ Optimizador JS Simple - Cargado exitosamente');