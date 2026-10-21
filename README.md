# 🥐 Panadería San Michell — Sistema de Control de Distribuidores, Facturas y Gastos

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/deborafernandas/panaderia-san-michell)

Aplicación web comercial desarrollada con **Python (Flask)**, **SQLite** y **Chart.js** para administrar los proveedores/distribuidores, pedidos e ingreso de facturas de la **Panadería San Michell**.

## ✨ Funcionalidades Principales

1. **Gestión de Distribuidores:**
   - Registro de distribuidores con nombre de empresa, RUT/ID, teléfono y rubro/insumos que provee (ej. Harinas, Lácteos, Repostería).
2. **Ingreso de Facturas por Pestañas (Diarias, Semanales y Mensuales):**
   - Clasificación manual mediante pestañas interactivas según si la factura corresponde a un gasto **Diario**, **Semanal** o **Mensual**.
   - Registro de **Número de Factura**, **Fecha de emisión**, **Detalle del pedido**, **Monto a cancelar** y **Medio de pago** (`Efectivo`, `Cheque` o `Transferencia`).
3. **Gráficos Interactivos y Comparación de Gastos a Fin de Mes por Distribuidor:**
   - **Gráfico de Barras Agrupadas (Chart.js):** Compara visualmente cuánto se gastó en cada distribuidor separado por Facturas Diarias, Semanales y Mensuales, mostrando además el total de pedidos al pasar el cursor.
   - **Gráfico de Dona (Chart.js):** Muestra la proporción del gasto mensual según el medio de pago utilizado (`Efectivo`, `Cheque`, `Transferencia`).
   - **Tabla de Cierre Mensual:** Agrupada por distribuidor (`GROUP BY`), permitiendo comparar la cantidad de pedidos realizados en el mes, el detalle de lo pedido y qué porcentaje del presupuesto mensual representa cada proveedor.

## ☁️ Despliegue Gratis 24/7 en Render

Este repositorio ya incluye configuración automática (`render.yaml` y `gunicorn`). Para publicarlo permanentemente en la nube gratis:
1. Haz clic en el botón morado **Deploy to Render** de arriba (o entra a [dashboard.render.com/blueprint/new](https://dashboard.render.com/blueprint/new)).
2. Inicia sesión con tu cuenta de GitHub (`deborafernandas`).
3. Selecciona el repositorio `panaderia-san-michell` y presiona **Apply**.

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
