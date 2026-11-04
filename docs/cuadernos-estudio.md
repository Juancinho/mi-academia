# Cuadernos de estudio

En la web privada, **Estudiar** reúne el material de cada sesión en un cuaderno. Puedes buscar por título, tema, apuntes o referencias. Desde el cuaderno se puede leer, consultar conceptos e historial, revisar las fuentes y practicar varias actividades seguidas.

## Apuntes a partir de conversaciones

La conexión de Mi Academia pide a ChatGPT que elabore `study_notes` al registrar aprendizaje sustancial: objetivos, apartados explicativos, ejemplos o procedimientos cuando proceda, glosario y dudas abiertas. Cada apartado indica sus fuentes y los conceptos locales relacionados. También pide varias actividades complementarias adaptadas al contenido, evitando preguntas repetidas y relleno.

Los apuntes admiten Markdown, listas, tablas, código y fórmulas LaTeX delimitadas por `$` o `$$`. El HTML incrustado se omite y las imágenes remotas no se cargan automáticamente. Las URL ejecutables y enlaces con credenciales se bloquean en el lector.

Esto funciona cuando ChatGPT dispone de la conexión y del contenido de la conversación. La plataforma no recupera chats privados por su cuenta ni llama a una API de pago para inventar apuntes ausentes.

Las sesiones antiguas también aparecen en Estudiar: si no contienen apuntes, se organizan sus conocimientos guardados como apartados. Esa vista se etiqueta como material organizado, sin afirmar que ha sido reelaborado por IA. Desde **Editar apuntes** se pueden desarrollar los textos, añadir apartados, objetivos, términos y dudas, manteniendo las referencias de la sesión.

## Fuentes y original

La pestaña **Referencias** conserva títulos, enlaces, citas, fragmentos y localizadores. La naturaleza epistemológica de cada concepto distingue hechos verificables, interpretaciones, opiniones y contenidos cambiantes. Una referencia a ChatGPT documenta procedencia; no equivale a una verificación independiente.

La pestaña **Conversación** muestra exclusivamente el original aportado durante la importación. Editar los apuntes no modifica ese original, la identidad de los conocimientos ni las tarjetas FSRS. La edición usa un número de versión para impedir que dos ventanas sobrescriban cambios sin detectarlo. Para añadir fuentes, conocimientos o ejercicios nuevos se registra una ampliación con otro `external_id`.

## Tandas de práctica

**Practicar** prepara las actividades del cuaderno. También se puede trabajar toda la biblioteca o filtrar por tipo: recuperación, explicación, razonamiento, comparación, análisis, demostración y práctica.

El progreso de la tanda muestra cuántas actividades has evaluado durante esa visita. Después de fijar una respuesta se revelan la referencia y los criterios. Al confirmar tu puntuación se guardan respuesta, errores e historial y se actualiza FSRS antes de pasar a la siguiente actividad. Las actividades futuras se pueden incluir expresamente; evaluarlas recalcula su próxima fecha. Cada ejercicio mantiene su propio calendario.

El progreso visual de la tanda se reinicia al recargar o cambiar de material; las evaluaciones y fechas quedan guardadas. Leer apuntes o terminar una tanda no implica dominio demostrado. La evaluación continúa siendo manual y confirmada por el usuario.

## Copias y compatibilidad

- **Descargar apuntes** exporta la versión actual en Markdown con bibliografía y procedencia.
- El respaldo completo de la nube incluye las ediciones de los cuadernos y su versión. Se restauran también respaldos anteriores que todavía no contienen cuadernos.
- El JSON de sesiones conserva el material original importado, incluidos sus `study_notes` iniciales cuando existen. Las ediciones posteriores se conservan en el respaldo completo y en Markdown; no se introducen silenciosamente en el original reimportable.
- El MVP Python admite importar, mostrar y exportar `study_notes` con el mismo contrato. El editor y las tandas de estudio están implementados en la web alojada.

Ejemplo reimportable: [`examples/cuaderno-estudio.json`](../examples/cuaderno-estudio.json). Instrucciones para obtenerlo desde una conversación: [`prompt-chatgpt.md`](prompt-chatgpt.md).
