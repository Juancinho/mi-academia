# GitHub y acceso desde ChatGPT

## Qué contiene este repositorio

El código de Mi Academia, las pruebas, la documentación, el esquema de importación y una sesión ficticia de ejemplo. La base SQLite de cada persona, sus exportaciones, copias y secretos quedan fuera del repositorio mediante `.gitignore`.

Publicar el código permite consultar y desarrollar el proyecto desde GitHub. No pone en marcha Streamlit en Internet ni sincroniza la biblioteca personal.

## Consultar el código desde ChatGPT

Si el repositorio es público, puedes proporcionar su enlace y pedir a ChatGPT que consulte archivos concretos cuando disponga de navegación o de herramientas de GitHub. Compartir un enlace no garantiza que lea todo el repositorio ni que lo recuerde entre conversaciones. Para el contrato de importación comparte `docs/academia-schema-v1.json` y `docs/prompt-chatgpt.md`.

Un repositorio privado puede consultarse mediante una conexión de GitHub autorizada con acceso a ese repositorio. El acceso efectivo depende de las herramientas disponibles en ese chat y de los permisos de la cuenta conectada. Comprueba la conexión pidiendo que lea el README; no presupongas que los permisos de un chat están disponibles en todos los demás.

La [documentación oficial sobre plugins y conexiones](https://learn.chatgpt.com/docs/plugins) explica el uso de cuentas conectadas y los permisos. No necesitas publicar tus datos personales para trabajar en el código con ChatGPT.

## Consultar o actualizar tu biblioteca personal

El SQLite permanece en tu equipo. Subir el código a GitHub no da a ChatGPT acceso a los conocimientos, respuestas, repasos ni sesiones que registres después.

El flujo actual para tus conocimientos es explícito: elige qué conversación convertir en JSON e impórtala en la app; o exporta los datos que quieras compartir y adjúntalos al chat correspondiente.

Para consultar o actualizar la biblioteca directamente habría que implementar una API o herramientas MCP autenticadas, con operaciones de búsqueda, importación y evaluación delimitadas. La conectividad al equipo local y la autorización serían parte de esa integración. Esa capacidad todavía no está implementada; el [plan de evolución](evolucion.md) explica la ruta prevista.
