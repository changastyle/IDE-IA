# Merge vs Squash — qué hicimos y qué vamos a hacer

## Qué hicimos esta vez

Laburamos en `feature/perro-gato`, commiteamos todo ahí, nos pasamos a `main`
y mergeamos. Como `main` no tenía commits nuevos desde que creamos la rama,
git hizo **fast-forward**: movió el puntero de `main` hasta el último commit
de la rama y listo. Después pusheamos.

```
antes:   main ── be4b8ca
                    \
perro-gato:          ── 19911d9 ── a4f8edc

después: main = perro-gato ── be4b8ca ── 19911d9 ── a4f8edc
```

**Resultado:** todos los commits de la rama quedaron en `main`, uno por uno.
Válido, pero ensucia el historial de `main` con commits de trabajo tipo
"por trabajar en la terminal" o "vamos a romper panel ia".

## La próxima: squash

Para no ensuciar `main`, la próxima vez que mergeemos una feature vamos a
hacer **squash**: todos los cambios de la rama entran a `main` como **un solo
commit** limpio, con un mensaje decente.

```bash
git checkout main
git merge --squash feature/loquesea   # baja el diff y lo deja stageado
git commit -m "feature loquesea: qué hace"   # un solo commit en main
git push origin main
```

Idea: *me quedo con el resultado, no con el historial de cómo llegué*. Los
commits intermedios quedan en la rama si algún día hace falta mirarlos.

## Ojo con el squash

- El commit squash **no registra de qué rama vino** — para git es un commit
  común y corriente.
- La rama **no queda marcada como mergeada**: `git branch --merged` no la
  muestra y para borrarla hay que usar `git branch -D` (forzado), no `-d`.

## Las tres formas de integrar una rama

| Estrategia | Comando | Qué pasa |
|---|---|---|
| **Merge** | `git merge rama` | Pasan todos los commits. Si main avanzó, crea merge commit; si no, fast-forward. |
| **Squash** | `git merge --squash rama` | Todo el diff de la rama → un solo commit en main. |
| **Rebase** | `git rebase main` (en la rama) | Reescribe los commits de la rama arriba de main, después fast-forward. |

## Si algún día queremos el merge commit explícito

Para que quede asentado qué rama se integró (aunque sea fast-forward):

```bash
git merge --no-ff feature/loquesea
```

## Si ya mergeamos y queremos convertirlo en squash

Solo si nadie más pulleó `main` (es destructivo, reescribe el remoto):

```bash
git reset --hard <commit-antes-del-merge>
git merge --squash feature/loquesea
git commit -m "mensaje único"
git push --force origin main
```
