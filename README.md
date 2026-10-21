# 🥐 Panadería San Michell — Sistema de Control de Distribuidores, Facturas y Gastos

Aplicación web comercial desarrollada con **Python (Flask)** y **SQLite** para administrar los proveedores/distribuidores, pedidos e ingreso de facturas de la **Panadería San Michell**.

## ✨ Funcionalidades Principales

1. **Gestión de Distribuidores:**
   - Registro de distribuidores con nombre de empresa, RUT/ID, teléfono y rubro/insumos que provee (ej. Harinas, Lácteos, Repostería).
2. **Ingreso de Facturas por Pestañas (Diarias, Semanales y Mensuales):**
   - Clasificación manual mediante pestañas interactivas según si la factura corresponde a un gasto **Diario**, **Semanal** o **Mensual**.
   - Registro de **Número de Factura**, **Fecha de emisión**, **Detalle del pedido**, **Monto a cancelar** y **Medio de pago** (`Efectivo`, `Cheque` o `Transferencia`).
3. **Comparación de Gastos y Balance a Fin de Mes por Distribuidor:**
   - Tarjetas superiores con el resumen comparativo entre gastos diarios, semanales y mensuales, además del desglose por medio de pago.
   - Tabla de cierre mensual agrupada por distribuidor (`GROUP BY`), permitiendo comparar la cantidad de pedidos realizados en el mes, el detalle de lo pedido, cuánto se pagó en efectivo/cheque/transferencia y qué porcentaje del presupuesto mensual representa cada proveedor.

## 🚀 Cómo ejecutar el proyecto en tu computador

1. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Iniciar el servidor de Flask:**
   ```bash
   python app.py
   ```

3. **Abrir en el navegador:**
   Ingresa a `http://127.0.0.1:5000`
