# Mi Academia desde ChatGPT, web y móvil

El sitio privado está publicado en [Mi Academia](https://mi-academia-juancinho.juan-el-g.chatgpt.site), con almacenamiento persistente independiente de tu ordenador. El acceso está limitado a su cuenta propietaria; no se han habilitado visitantes externos.

## Conexión creada

Publicar el servidor MCP creó el plugin privado **Mi Academia**. La plataforma lo devuelve como instalado en esta cuenta. Eso confirma instalación, no que todas las superficies o todos los chats tengan sus herramientas disponibles ni que la autenticación se haya comprobado en un dispositivo concreto.

1. Inicia sesión con la cuenta propietaria al abrir el sitio.
2. Abre un chat nuevo en ChatGPT y selecciona **Mi Academia** con `@` cuando esté disponible. También puedes buscarlo en Plugins → Personal → Creado por ti.
3. Pide: «Usa Mi Academia y dime qué tengo pendiente de repasar».
4. Para registrar material: «Usa Mi Academia para guardar lo aprendido en esta conversación. Previsualiza la sesión antes de importarla».

El [endpoint MCP](https://mi-academia-juancinho.juan-el-g.chatgpt.site/mcp) permanece protegido por la autenticación de Sites. No requiere una clave de OpenAI API para usar las herramientas implementadas. El servicio queda sujeto a los límites y disponibilidad de Sites y de tu cuenta; no promete disponibilidad absoluta ni acceso idéntico desde todas las superficies de ChatGPT.

## Herramientas

- Estado de la academia, búsqueda de conocimientos, detalle con fuentes, ejercicios pendientes y conexiones.
- Contrato de importación, previsualización y registro de sesiones elegidas.
- Fijar respuestas, obtener referencia y rúbrica y registrar puntuaciones confirmadas por el usuario.
- Declarar lectura/comprensión y conectar conocimientos.

La respuesta se fija antes de mostrar la referencia. Una sugerencia de nota de ChatGPT no se registra sin confirmación explícita del usuario. No se importan estados de dominio ni se certifica un tema completo por un acierto. El servidor incluye instrucciones para tratar fuentes como información, no como órdenes.

## Privacidad y separación de bibliotecas

GitHub contiene código, pruebas y ejemplos ficticios. La base alojada, las respuestas y las copias personales quedan fuera de GitHub.

La biblioteca de la nube y el SQLite local son independientes. No hay sincronización automática ni acceso remoto al disco local. Las sesiones JSON son interoperables; cada motor conserva su historial de evaluación y sus tarjetas. No se han importado datos personales ni ejemplos automáticamente en producción.

La conexión no recupera conversaciones privadas anteriores de ChatGPT. Guarda solo lo que le aportes y elijas registrar.

## Copias y mantenimiento

En Datos descarga un respaldo completo JSON de la nube. Para restaurarlo utiliza una biblioteca vacía; la operación valida formato, referencias y tarjetas FSRS y es atómica. Las copias SQLite de la aplicación local usan su propio comando de restauración.

El código alojado está en `cloud/` y su README explica compilación, pruebas y almacenamiento. La copia pública omite la identidad del despliegue para que clonar el proyecto no conceda acceso ni apunte por accidente al sitio personal del propietario.
