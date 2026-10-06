# Prime ChainSentinel v0.7

Prime ChainSentinel es un producto de software orientado a conservar, clasificar y reutilizar evidencia computacional y probabilística mediante un contrato de procedencia. El sistema distingue evidencia observada de estimaciones, correcciones, simulaciones y cargas sustitutas, y conserva sus fuentes y relaciones de derivación.


## Flujo de uso

El flujo computacional está guiado por evidencia:

```text
Importar evidencia
  -> validar y registrar artefactos
  -> comprobar integridad SHA-256
  -> consultar procedencia
  -> ejecutar laboratorios
  -> conservar resultados derivados
  -> exportar reporte
```

Las vistas de Hardware, GPU, Hash y Merkle, así como las simulaciones blockchain que dependen de líneas base, utilizan evidencia computacional previamente importada. En una instalación limpia no se muestran métricas MI300X incrustadas ni se ejecutan esos laboratorios sin evidencia compatible.

El flujo financiero parte de una consulta explícita del usuario:

```text
Consultar mercado
  -> registrar las series observadas
  -> ejecutar Monte Carlo sobre esas mismas series
  -> comparar motores sobre la misma evidencia de mercado
  -> exportar únicamente los resultados realmente ejecutados
```

La sección **Reportes** no vuelve a consultar el mercado ni ejecuta simulaciones o comparaciones en segundo plano.

## Componentes

- **Frontend:** React + Vite + Tailwind + Recharts.
- **Backend:** FastAPI + Pandas + NumPy + ReportLab.
- **Persistencia de procedencia:** SQLite.
- **Entidades principales:** `imports`, `source_artifacts`, `results` y `derivations`.
- **Clases de evidencia:** `MEASURED`, `SURROGATE`, `ESTIMATED`, `CORRECTED`, `SIMULATED`, `EXPERIMENTAL`.
- **Importación:** ZIP, JSON, CSV y TXT compatibles.
- **Integridad:** SHA-256 del paquete y de los artefactos almacenados.
- **Reportes:** PDF generado por el backend a partir de resultados ya producidos.

## Inicio rápido

Abra dos terminales desde la raíz del proyecto.

### Backend

```bash
cd backend
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Backend:

```text
http://localhost:8000
```

Documentación de la API:

```text
http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend:

```text
http://localhost:5173
```


## Probar el flujo computacional

La carpeta `sample_data` incluye una campaña para probar el flujo de importación:

```text
sample_data/MI300X_Benchmarks.zip
```

Desde la interfaz:

1. Abra **Evidencia**.
2. Importe `MI300X_Benchmarks.zip`.
3. Revise la importación, los artefactos y los resultados registrados.
4. Abra Hardware, GPU, Hash, Merkle o Blockchain.
5. Compruebe que las vistas muestran la fuente activa y que los resultados derivados conservan su linaje.
6. Genere el reporte desde **Reportes** cuando quiera documentar los resultados ejecutados.

El paquete importado se conserva sin modificación. Los archivos extraídos se registran como artefactos fuente con sus respectivos hashes.

## Flujo financiero

Prime ChainSentinel no carga una cartera predeterminada al iniciar. El usuario debe definir los símbolos y pesos y ejecutar primero **Mercado**.

1. Abra **Mercado**.
2. Defina los activos, pesos y período histórico.
3. Pulse **Consultar mercado**.
4. Las series adquiridas quedan registradas con identificadores de evidencia.
5. Continúe a **Monte Carlo**; la simulación reutiliza exactamente esas series registradas.
6. Continúe a **Comparación**; los motores utilizan la misma evidencia de mercado.
7. Abra **Reportes**; el PDF solo incluye las etapas financieras que hayan sido ejecutadas.

La semilla pseudoaleatoria no se presenta como variable de análisis en la interfaz. Se mantiene internamente como metadato técnico de reproducibilidad cuando un procedimiento estocástico la requiere.

## Datos de mercado

El frontend no consulta directamente proveedores externos. El flujo normal es:

```text
Frontend -> FastAPI -> Yahoo Finance -> registro de evidencia -> respuesta normalizada
```

El proveedor se controla mediante:

```text
MARKET_DATA_PROVIDER=yahoo
MARKET_CACHE_TTL_MINUTES=60
```

En el modo normal de la tesis, si Yahoo Finance no está disponible y no existe una copia observada previamente registrada, la aplicación informa el error. No sustituye silenciosamente la consulta por datos sintéticos.

El modo sintético permanece disponible únicamente si se configura de forma explícita para pruebas fuera de línea.

## Integridad y procedencia

Un SHA-256 coincidente permite comprobar que los bytes almacenados son iguales a los registrados durante la ingesta. Esto **no demuestra por sí mismo la autenticidad del productor ni la veracidad del contenido**.

Prime ChainSentinel distingue cuatro aspectos:

- **integridad:** coincidencia del digest registrado;
- **origen registrado:** fuente, campaña y artefacto asociados;
- **contrato:** metadatos y reglas que debe cumplir un resultado;
- **linaje:** relación entre resultados antecedentes y resultados derivados.

## API de procedencia

Entre las rutas principales se encuentran:

```text
POST /api/imports
GET  /api/imports
GET  /api/imports/{import_id}
GET  /api/provenance/summary
GET  /api/provenance/results
GET  /api/provenance/results/{result_id}
GET  /api/provenance/artifacts/{artifact_id}
GET  /api/provenance/artifacts/{artifact_id}/verify
```

Los laboratorios blockchain rechazan la operación cuando no existe una línea base importada compatible.

## Reporte PDF

La sección **Reportes** utiliza:

```text
POST /api/reports/generate
```

El reporte se genera en español y representa el estado de la sesión y los resultados ya ejecutados. No realiza nuevas consultas financieras ni lanza Monte Carlo o comparación de motores de manera implícita.

Puede incluir, cuando corresponda:

- fuente computacional activa;
- identificador de importación y campaña;
- SHA-256 del paquete;
- perfil del entorno importado;
- evidencia GPU, Hash, Merkle y PoW;
- consulta de mercado realizada;
- simulación Monte Carlo realizada;
- comparación de motores realizada;
- metadatos de reproducibilidad;
- límites de interpretación.

Si una etapa no fue ejecutada, el reporte la identifica como **NO EJECUTADA** en lugar de generar resultados por cuenta propia.

## Pruebas funcionales del backend

Desde `backend`:

```bash
python -m unittest discover -s tests -v
```

Las pruebas cubren, entre otros puntos:

- rechazo de resultados derivados sin linaje;
- bloqueo de laboratorios blockchain sin evidencia importada;
- creación de resultados con linaje después de importar una campaña;
- ingesta CSV;
- verificación SHA-256 y detección de alteraciones;
- rechazo de rutas ZIP inseguras;
- registro de procedencia financiera.

## Nota sobre la evidencia original

Los artefactos fuente incluidos dentro de una campaña importada no deben editarse para cambiar etiquetas, autores u otros metadatos históricos. Prime ChainSentinel preserva la evidencia original y realiza la normalización y clasificación en registros separados.

