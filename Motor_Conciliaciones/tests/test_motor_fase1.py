import sys
import os

from src.core.models import Transaccion
from src.core.engine import ReconciliationEngine

def test_multifase():
    print("🧪 TEST INTEGRAL DE TODAS LAS FASES")
    
    datos = [
        # Datos para Fase 1 (1 a 1)
        Transaccion(1, "F1: Pago A", "C1", 100, 1),
        Transaccion(2, "F1: Recibo A", "C1", -100, 1),
        
        # Datos para Fase 2 (1 a N: 500 = 200 + 300)
        Transaccion(3, "F2: Pago Grande", "C1", 500, 1),
        Transaccion(4, "F2: Factura part1", "C1", -200, 1),
        Transaccion(5, "F2: Factura part2", "C1", -300, 1),
        
        # Datos para Fase 3 (N a N: 150 + 50 = 120 + 80)
        Transaccion(6, "F3: Pago 1", "C1", 150, 1),
        Transaccion(7, "F3: Pago 2", "C1", 50, 1),
        Transaccion(8, "F3: Gasto 1", "C1", -120, 1),
        Transaccion(9, "F3: Gasto 2", "C1", -80, 1),
        
        # Datos que deben quedar PENDIENTES (Fase 4)
        Transaccion(10, "Huérfana", "C1", 999, 1)
    ]

    motor = ReconciliationEngine()
    conciliadas, pendientes = motor.ejecutar_proceso_completo(datos)

    print("\n--- REPORTE FINAL ---")
    print(f"Grupos Conciliados: {len(conciliadas)}")
    print(f"Transacciones Pendientes: {len(pendientes)}")
    
    # Verificación
    assert len(pendientes) == 1, "Debería quedar solo 1 pendiente"
    assert any("Huérfana" in t.descripcion for t in pendientes)
    print("\n🔥 ¡EL MOTOR ES UNA BESTIA! Todas las fases pasaron la prueba.")

if __name__ == "__main__":
    test_multifase()