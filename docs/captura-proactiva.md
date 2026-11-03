# Captura proactiva de conocimientos — Mi Academia

La conexión privada incorpora las reglas del propietario para intentar registrar aprendizaje sustancial de cualquier materia, sin esperar una petición de guardado para cada sesión.

## Reglas configuradas

1. Detecta proactivamente oportunidades de aprendizaje. No esperes a que el usuario diga «guárdalo».
2. Responde normalmente a su pregunta, con el rigor y profundidad habituales.
3. Cuando haya conocimientos sustanciales, identifica los conceptos, hechos, procedimientos y relaciones más importantes.
4. Consulta Mi Academia cuando sea útil para evitar duplicados y conectar el nuevo aprendizaje con el existente.
5. Genera preguntas de recuperación, razonamiento o aplicación según la naturaleza del contenido.
6. Utiliza las herramientas de Mi Academia para validar y registrar el aprendizaje cuando estén disponibles y las autorizaciones lo permitan.
7. Respeta las confirmaciones que exijan las herramientas. Si no has podido guardar algo, no afirmes que está registrado.
8. Conserva las fuentes y distingue hechos verificables, interpretaciones y conocimientos cambiantes.
9. Registra los contenidos nuevos como pendientes de consolidar. No supongas que el usuario ya los domina.
10. No llenes la academia de dudas triviales, instrucciones operativas o conversaciones sin valor educativo.
11. Evita interrumpir las explicaciones con procedimientos administrativos de guardado.

El objetivo es que la captura sea automática y transparente cuando las herramientas estén disponibles, sin convertirse en una carga para el usuario.

## Aplicación en la conexión

Las reglas se entregan en `instructions` durante `server/discover` e `initialize`, y las herramientas de búsqueda, previsualización e importación describen cuándo usarlas proactivamente. La web permite consultar las reglas en Conectar ChatGPT. La política está versionada en `cloud/lib/capture-policy.ts` y el servidor se identifica como versión 0.2.1.

El flujo indicado es: responder → identificar aprendizaje sustancial → consultar duplicados cuando sea útil → preparar fuentes y ejercicios → validar con `preview_import` → registrar con `import_session` si las autorizaciones lo permiten. La validación no añade por sí misma una petición administrativa al usuario; se mantienen todas las confirmaciones que exijan la herramienta o la plataforma.

El estado inicial «Registrado» significa pendiente de consolidar. La captura no marca lectura, comprensión ni dominio, ni puntúa como si el usuario hubiera respondido a un ejercicio. Para evaluar un repaso sigue siendo necesaria la confirmación expresa de la puntuación.

## Alcance

Esta es una instrucción persistente de Mi Academia, no un cambio de las instrucciones globales de la cuenta de ChatGPT. Se aplica cuando un chat carga la conexión y tiene sus herramientas disponibles. No accede a conversaciones privadas no aportadas, no ejecuta una captura en segundo plano de toda la cuenta y no garantiza que cada modelo invoque siempre las herramientas.

Tras actualizar, abre un chat nuevo con Mi Academia. Si un chat sigue mostrando metadatos antiguos, actualiza la conexión desde su página de Plugins. Las pruebas automatizadas comprueban que la política se entrega por ambos métodos MCP y que las herramientas siguen conservando sus permisos y confirmaciones.
