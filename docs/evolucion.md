# Plan de evolución

La web alojada ya incluye conexión MCP con ChatGPT, captura proactiva, cuadernos estructurados y tandas de estudio. La versión local admite importar y mostrar los apuntes. Las siguientes etapas describen ampliaciones pendientes; conservan la importación manual y el funcionamiento local.

## 1. Uso real y calidad de la biblioteca

- Añadir archivado de ejercicios y conocimientos con histórico intacto, edición mediante versiones y enlaces `sustituye_a`.
- Sugerir posibles duplicados, mostrando diferencias, fechas y fuentes antes de fusionar. Conservar todas las evidencias e intentos.
- Añadir cobertura por competencia y más de un ejercicio de transferencia, evitando confundir dominio de una pregunta con dominio general.
- Paginación, FTS5 y exploración limitada a vecinos para bibliotecas grandes.
- Reconstruir evolución histórica del dominio a partir de intentos y estados FSRS, con la versión de la regla de dominio identificada.

**Criterio para completar:** actualizar o archivar contenido sin perder la relación entre una respuesta histórica, el ejercicio que la produjo y sus fuentes.

## 2. Integración explícita con ChatGPT

El flujo local es conversación → JSON revisado → importación. En la web ya funciona la conexión MCP privada para consultar e importar sesiones y editar cuadernos. La aplicación no puede asumir acceso al historial privado de ChatGPT.

- Crear un adaptador para archivos de conversaciones que el usuario haya exportado y seleccionado expresamente. Mantener identificadores de conversación y turno, conservar el texto y no enviar automáticamente el archivo completo a ningún proveedor.
- Añadir una API local o servidor MCP con herramientas pequeñas: previsualizar importación, importar una sesión y consultar conocimientos. Aplicar el mismo validador, deduplicación y transacciones del servicio actual.
- Estudiar una integración mediante herramientas o acciones compatibles con el producto elegido. El acceso desde servicios remotos al equipo local exige una solución de conectividad y autenticación explícita; `localhost` no es accesible desde un servicio remoto por defecto.
- Mostrar al usuario el material que se enviará. Si se usa una API con coste, hacerlo opcional y mantener el camino gratuito manual; un modelo local sería otra opción.

**Criterio para completar:** una conversación elegida puede convertirse en una sesión trazable sin importar historial no seleccionado, y reenviarla no duplica conocimientos ni intentos.

## 3. Notificaciones y copias programadas

- Añadir un comando `due-summary` que lea pendientes y devuelva un resumen sin abrir Streamlit.
- Ejecutarlo con el Programador de tareas de Windows, con zona horaria, franja de silencio y límites de frecuencia.
- Notificar solo si hay repasos pendientes y evitar avisos duplicados durante la misma franja. El fallo de un aviso no debe cambiar la planificación FSRS.
- Programar copias mediante el mismo mecanismo, con rotación, ubicación elegida y prueba de restauración periódica.
- Si se añade correo u otro canal, configurarlo expresamente; no enviar mensajes por defecto.

**Criterio para completar:** recibir un aviso cuando toca, sin necesitar una pestaña abierta, con registro de ejecución y sin alterar tarjetas al consultar pendientes.

## 4. Evaluación automática asistida

- Introducir una interfaz `Evaluator` que devuelva puntuación sugerida, criterios satisfechos, errores, justificación e incertidumbre.
- Mantener la respuesta original y guardar proveedor/modelo, versión del prompt, rúbrica, entradas y resultado. La tabla de intentos ya reserva la identidad del evaluador; una migración añadirá la información específica de cada ejecución.
- Empezar con sugerencias revisables por el usuario. Registrar el resultado elegido como intento solo una vez confirmado; no convertir una salida incierta en dominio demostrado.
- Comparar el corrector contra un conjunto de respuestas humanas: correctas, parciales, incorrectas y alternativas razonadas. Medir errores por modalidad, especialmente en interpretaciones y opiniones.
- Para matemáticas o código, combinar criterios con comprobaciones deterministas apropiadas. Si se ejecuta código, hacerlo en un entorno aislado diseñado para ello; actualmente el texto nunca se ejecuta.
- Separar generación de ejercicios de evaluación de respuestas, para evitar evaluar únicamente coincidencia con una frase generada.

**Criterio para completar:** las sugerencias tienen trazabilidad y se han evaluado contra ejemplos humanos; el usuario puede corregirlas sin perder el resultado original.

## 5. Recuperación de fuentes y cambios en el conocimiento

- Añadir recuperación explícita de fuentes identificadas, guardando URL, fecha, localizador, fragmento y versión o huella del contenido.
- Marcar contradicciones o material vencido para revisión, sin reemplazar silenciosamente afirmaciones o soluciones antiguas.
- Separar comprobar actualidad/veracidad de repasar memoria. Una respuesta puede recordar bien una afirmación desactualizada.
- Conservar la distinción entre hechos, interpretaciones, opiniones y contenido cambiante en extracción, búsqueda y evaluación.

**Criterio para completar:** cualquier afirmación actualizada conserva procedencia y fecha, y las evaluaciones señalan con qué versión se realizaron.

## 6. Personalización y otros dispositivos

Con suficientes intentos, valorar optimización de parámetros FSRS por usuario y comparar resultados antes de activarla. Mantener configuraciones anteriores en el historial y proporcionar una reprogramación explícita y respaldada.

Solo si surge necesidad real: añadir API autenticada, otro frontend, sincronización y almacenamiento de servidor. La lógica de aprendizaje seguirá en el núcleo, con migraciones y pruebas de contratos; no hace falta introducir esos servicios para el uso local actual.
