import os
from src.data.db_manager import DatabaseManager
from src.core.engine import ReconciliationEngine
from src.utils.reporter import ReconciliationReporter

if __name__ == "__main__":
    # Configuración inicial
    NOMBRE_DB = "conciliacion.db"
    CUENTA_A_CONCILIAR = "110505"
    CARPETA_REPORTES = "reportes"

    # Crear carpeta de reportes si no existe
    if not os.path.exists(CARPETA_REPORTES):
        os.makedirs(CARPETA_REPORTES)

    # Inicializar componentes
    db = DatabaseManager(NOMBRE_DB)
    engine = ReconciliationEngine()
    reporter = ReconciliationReporter(ruta_salida=f"{CARPETA_REPORTES}/")

    print(f"--- 🔍 Iniciando Proceso para Cuenta: {CUENTA_A_CONCILIAR} ---")

    # 1. Cargar datos pendientes de la DB
    filas_crudas = db.obtener_pendientes(CUENTA_A_CONCILIAR)
    
    if not filas_crudas:
        print("📭 No hay transacciones pendientes para esta cuenta.")
    else:
        # 2. Convertir tuplas a objetos Transaccion
        transacciones = engine.convertir_a_modelos(filas_crudas)

        # 3. ¡EL MOTOR ENTRA EN ACCIÓN!
        conciliadas, pendientes = engine.ejecutar_proceso_completo(transacciones)

        # 4. PERSISTENCIA: Guardar los resultados en la DB
        if conciliadas:
            db.registrar_conciliacion_masiva(conciliadas)
        
        # 5. GENERAR PRODUCTO FINAL (Excel)
        ruta_archivo = reporter.generar_excel_final(conciliadas, pendientes)

        # 6. RESUMEN FINAL
        print(f"\n" + "="*30)
        print(f"✨ RESULTADOS FINALES ✨")
        print(f"✅ Transacciones Conciliadas: {sum(len(g) for g in conciliadas)}")
        print(f"⚠️ Transacciones Pendientes: {len(pendientes)}")
        print(f"📂 Reporte disponible en: {ruta_archivo}")
        print("="*30)