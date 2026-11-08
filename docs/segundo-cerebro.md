# Segundo cerebro: conversaciones, cuadernos y Obsidian

## Qué hace la plataforma

- **Conversaciones:** índice de texto completo FTS5 con búsqueda por título y mensajes, lector por turnos, filtro dentro del chat, enlace original cuando se conoce y cuadernos vinculados.
- **Material ya subido:** se indexa el texto original aportado; si no existe, se conservan los fragmentos o el resumen disponibles con la etiqueta «Solo fragmentos o resumen». La indexación no reconstruye chats ausentes.
- **Exportaciones ChatGPT:** importa `conversations.json`, eligiendo qué chats subir. El archivo se analiza en el navegador y solo se envía la selección. Se sigue `current_node` hacia sus padres para conservar la rama activa; no se mezclan versiones alternativas de respuestas. Los adjuntos sin texto se omiten con avisos. Máximo 50 MB por archivo, 1,5 MB por conversación y 50 conversaciones por llamada; el navegador las procesa por tandas de cinco.
- **Cuadernos:** objetivos, explicaciones, derivaciones, ejemplos resueltos, síntesis, glosario, dudas y referencias. Markdown, LaTeX y diagramas Mermaid. La indicación de extensión y estructura no es una evaluación de exactitud ni dominio.
- **Grafo:** conceptos y cuadernos, enlaces explícitos con explicación, procedencia, búsqueda, arrastre, zoom y vecindarios de uno o dos saltos. Se muestran hasta 400 nodos en la vista; el límite solo afecta al dibujo. Las etiquetas compartidas no se presentan como relaciones causales.

Las herramientas adicionales son `index_conversations`, `search_conversations`, `get_conversation`, `get_study_brief` y `get_knowledge_graph`. Las sesiones, los repasos y sus reglas de dominio conservan su funcionamiento anterior. Las conversaciones tienen historial de versiones y se incluyen en el respaldo; FTS es un índice derivado y se reconstruye con los triggers al restaurar.

La pestaña Conversaciones también ofrece `index_conversations` mediante WebMCP cuando el navegador lo admite. Usa la misma validación y API autenticada que la interfaz, permite vincular turnos aportados con cuadernos existentes y muestra el resultado del registro. Solo está disponible con esa vista abierta: no observa otros chats en segundo plano ni añade acceso al historial.

## Elaboración real de apuntes

La generación la realiza el modelo del chat, con las herramientas de Mi Academia disponibles. `get_study_brief` recupera material y criterios para desarrollar el tema; `save_notebook` guarda el resultado con control de versión. El botón «Preparar desarrollo con ChatGPT» copia una petición concreta para ese cuaderno: **copiarla no genera apuntes ni ejecuta un modelo en segundo plano**.

No hay una API de pago configurada ni un generador ficticio que amplíe automáticamente texto en el servidor. Los apuntes antiguos inicialmente organizados como fichas se etiquetan como desarrollo inicial. El modelo puede convertirlos en capítulos de tutor utilizando las fuentes disponibles, señalando lo que queda por verificar. Los ejemplos y diagramas elaborados se distinguen de citas literales.

## Captura automática: alcance real

La conexión comunica el deseo de capturar aprendizaje sustancial y ahora pide también indexar los turnos aportados y producir material didáctico completo. La habilidad incluida en `integrations/mi-academia-study` permite selección implícita por afinidad con preguntas de estudio. Requiere la conexión privada Mi Academia ya instalada.

La habilidad se puede instalar en Codex copiando `skills/mi-academia-aprender` a la carpeta de habilidades del usuario. El paquete de plugin contiene una habilidad, no una conexión nueva ni credenciales. En ChatGPT se puede crear la misma habilidad desde Complementos → Habilidades → Añadir → Crear con el editor, copiando nombre, descripción e instrucciones del SKILL.md. Verifica que aparezca en Instaladas. El paquete de plugin es una alternativa de distribución para entornos compatibles. La selección implícita depende del entorno, las herramientas y la pregunta; no garantiza observar todos los chats. Las instrucciones MCP por sí solas tampoco convierten la aplicación en un observador global del historial privado.

Se respetan permisos y confirmaciones. Una captura fallida no se presenta como guardada. No se registran automáticamente conversaciones operativas o triviales, ni se supone dominio por haber leído.

## Obsidian en Windows

La sincronización es **nube → vault**. No sube el resto del vault ni modifica sus notas personales. Dentro del vault crea:

```text
Mi Academia/
  00 Inicio/
  01 Temas/
    Economía y finanzas/
      Cuadernos/
      Conceptos/
      Conversaciones/
      Mapas/
    Energía e ingeniería/
      ...
    Tecnología e informática/
      ...
  02 Fuentes/
```

Solo se crean áreas con contenido. Las carpetas representan áreas amplias, nunca cada etiqueta: los temas específicos se conservan como propiedades, enlaces y mapas dentro de su área. Las sugerencias de archivo consideran todos los temas y el título; cuando no reconocen un tema usan su cuaderno de origen o «Por organizar». Las conversaciones se agrupan con sus cuadernos y las fuentes compartidas se conservan una sola vez. Cada área tiene una nota índice. Las áreas ordenan la exportación sin imponer una taxonomía a la biblioteca ni limitar temas nuevos.

Se pueden personalizar las asignaciones en `.vault-sync/config.json`, sin cambiar etiquetas ni relaciones de la web:

```json
"organization": {
  "topic_areas": {"Fiscalidad": "Economía y finanzas", "Mi tema nuevo": "Mi área"},
  "notebook_areas": {"identificador-del-cuaderno": "Mi área"}
}
```

Los mapas enlazan conceptos de cada tema. Los cuadernos enlazan conceptos, fuentes y conversaciones; los conceptos enlazan relaciones y cuadernos de origen. Son enlaces `[[...]]` de Obsidian, con LaTeX y Mermaid conservados en Markdown.

Los archivos tienen identificadores y nombres estables aunque cambie un título. La sincronización reorganiza las notas gestionadas en sus áreas y actualiza sus enlaces generados; comprueba los destinos antes de mover y no sobrescribe archivos ajenos. Solo retira carpetas vacías. Una nota editada localmente se traslada conservando su contenido: una actualización remota conflictiva se guarda como `*.nube-<hash>.md`. Los enlaces escritos a mano hacia rutas antiguas pueden necesitar actualización tras una reorganización. La ausencia de un elemento en el origen no elimina su archivo local. Las ediciones hechas en Obsidian no se fusionan de vuelta con la web en esta versión.

`academia.vault_sync` permite importar una copia offline para probar el flujo:

```powershell
.\.venv\Scripts\python.exe -m academia.vault_sync --vault 'D:\MiVault' --snapshot 'D:\copia-vault.json'
```

La instalación automática usa `node scripts/configure-vault.mjs <ruta-del-vault>` y `academia.install_sync`. El ejecutor programado es Python (`academia.vault_sync --config ...`), por lo que no requiere cambiar la política de ejecución de PowerShell. La credencial de servicio de Sites se entrega por stdin, se cifra con DPAPI para el usuario de Windows y se guarda en `.vault-sync`, ignorada por Git. La tarea «Mi Academia - Obsidian» ejecuta al iniciar sesión y cada 15 minutos mientras el usuario esté conectado; la red debe estar disponible. Un fallo de conexión no modifica notas; se reintenta en la siguiente ejecución. `last-result.json` contiene solo contadores o un error genérico, nunca cuerpos de notas ni credenciales.

## Frontera de acceso del puente privado

`/api/vault-sync` confía en el control **owner-private de Sites**, que valida el acceso de servicio antes de llegar al Worker. No transforma el token de servicio en identidad de visitante ni usa cabeceras de usuario inventadas. GET devuelve únicamente una copia de la academia; POST indexa los orígenes de sesiones existentes. El cliente no sigue redirecciones ni envía la credencial a otros destinos.

**No hacer público ni compartir este sitio mientras el puente esté habilitado.** Si en el futuro cambia la audiencia, hay que retirar el puente o añadir autorización propia por usuario antes de desplegar. El código público no incluye la credencial ni datos del vault. La revocación del acceso de servicio requiere volver a configurar la conexión local; no se elude una revocación.
