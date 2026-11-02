# Mi Academia · conexión privada con ChatGPT

Versión alojada del proyecto Mi Academia: biblioteca persistente, importación validada, fuentes, relaciones, evaluaciones y FSRS. El servicio funciona en Cloudflare Workers con D1 a través de Sites, independientemente del ordenador del usuario.

## Acceso y datos

- Sites mantiene el sitio privado para su propietario y autentica las peticiones. Conserva esta política; esta versión contiene una biblioteca por sitio, no un sistema multiusuario con bibliotecas separadas.
- Cada operación de datos exige la identidad validada que Sites adjunta. Las escrituras del navegador también verifican el origen. No se utiliza una clave secreta dentro del frontend.
- El endpoint `/mcp` publica 12 herramientas con protocolo 2026-07-28 y compatibilidad de inicialización anterior. Descubrimiento y listado describen las herramientas; las llamadas que consultan o cambian datos requieren identidad.
- Al publicar con la capacidad MCP, Sites crea una conexión privada instalable en ChatGPT. Su presencia en un chat depende de la cuenta y de los permisos disponibles. No se garantiza uso automático en todos los chats ni acceso a conversaciones no aportadas.
- El SQLite local y D1 son bibliotecas independientes. No hay sincronización automática. Importa explícitamente las sesiones que quieras conservar en la nube; a partir de ahí usa esa biblioteca como referencia desde ChatGPT y desde la web.

## Datos e importación

El contrato es el JSON Schema v1 del MVP Python. Se admiten los siete tipos de evaluación y etiquetas libres. La versión alojada limita un lote a 100 conocimientos, una sesión a 900 KB y una transacción a 900 elementos SQL. Los conflictos de external_id rechazan el lote completo. Los duplicados exactos agregan procedencia sin reiniciar los repasos.

`ts-fsrs@6.0.0` se configura expresamente con **FSRS-6**, retención 0,9, pasos 1m/10m, reaprendizaje 10m y sin fuzzing. No se migra silenciosamente al modelo FSRS-7 predeterminado. Los formatos internos de tarjeta del MVP Python y de esta versión son diferentes: las sesiones JSON son interoperables, el historial FSRS no se traslada automáticamente entre motores.

Una respuesta se fija antes de mostrar referencia y rúbrica. Para guardar una valoración desde ChatGPT el usuario debe confirmar expresamente la puntuación. Las respuestas con ayuda no cuentan como aciertos autónomos. El dominio provisional exige al menos dos aciertos separados por 24 horas en cada ejercicio, último intento correcto sin ayuda y recuerdo estimado >= 80 %.

## Copias

En Datos se puede exportar el respaldo completo JSON, incluyendo intentos, revisiones y tarjetas. La restauración solo funciona en una biblioteca completamente vacía y valida formato, referencias y estados FSRS dentro de una transacción. No admite archivos SQLite locales. El JSON de sesiones sirve para importar material original en cualquiera de las dos aplicaciones, sin transferir el aprendizaje posterior.

## Desarrollo en Windows

Requiere Node.js 24 o posterior. Desde este directorio:

```powershell
npm ci
npm test
npx tsc --noEmit
npm run build
```

Los validadores del contrato se generan durante prebuild para que el Worker no ejecute generación dinámica de código. No edites `lib/generated-validators.mjs` a mano: cambia el esquema o las definiciones y ejecuta `node scripts/generate-validators.mjs`.

Para vista previa usa `npm run dev`. La configuración portable simula una cuenta de desarrollo en localhost y no se incluye en producción. Antes de usar la base local aplica la migración de `drizzle/` con los comandos D1 del starter. Las migraciones publicadas son inmutables; las siguientes deben ser incrementales y conservar el historial.

## Verificación

18 pruebas Node con SQLite temporal cubren el contrato, los siete modos, importación atómica e idempotente, procedencia al deduplicar, estados, FSRS-6 y persistencia, respuestas fijadas, ayuda, confirmación, concurrencia, autorización, MCP y restauración. La base de pruebas nunca es la base personal alojada.

El navegador se comprueba además con una importación de ejemplo y un ciclo completo de evaluación. La producción arranca sin datos de demostración importados.
