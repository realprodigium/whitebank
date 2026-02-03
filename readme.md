# Bookmarks | Gestor de marcadores de X

Un dashboard minimalista para recopilar, organizar y explorar tus bookmarks de X (Twitter) con una interfaz limpia orientada a profesionales de datos e ingenieros.

## ¿Para quién está diseñado?

- **Analistas de datos** - Recopila referencias, artículos y análisis importantes
- **Ingenieros** - Almacena snippets, documentación y recursos técnicos
- **Investigadores** - Organiza fuentes y contenido relevante de forma sistemática
- **Profesionales técnicos** - Interfaz minimalista sin distracciones, al estilo Apple

## Función del proyecto

Este proyecto actúa como un puente entre X y tu flujo de trabajo personal:

1. **Autentica** con tu cuenta de X usando OAuth 2.0
2. **Sincroniza** tus bookmarks de forma segura
3. **Organiza** con búsqueda, filtrado y ordenamiento
4. **Explora** con una interfaz limpia y profesional

## Stack

- **Backend**: FastAPI (Python)
- **Frontend**: HTML5, CSS3, JavaScript vanilla
- **Base de datos**: SQLite3
- **API**: Twitter API v2 (X API)
- **Autenticación**: OAuth 2.0 con PKCE
- **UI**: Sistema de diseño minimalista (Apple-inspired)

## Requisitos de OAuth

Para que funcione correctamente, **necesitas estos scopes** en tu aplicación de X:

```
tweet.read          # Leer tweets y bookmarks (obligatorio)
users.read          # Obtener información del usuario (obligatorio)
bookmark.read       # Acceso a bookmarks (obligatorio a este contexto)
offline.access      # Generar refresh token (obligatorio)
```

Sin estos scopes, la API rechaza las solicitudes, incluso no autoriza la sesión del usuario.

## Limitaciones del plan gratuito de X

**Plan Free (actual)**:
- **1 solicitud cada 15 minutos** por usuario
- Máximo 100 bookmarks por solicitud
- Almacenamiento en caché de 5 minutos

### Status actual: Rate Limited

```
Límite: 100 solicitudes / 15 minutos
Uso actual: 160 solicitudes
Estado: EXCEDIDO
Reset: 22 de febrero, 2026
```

**Hasta el 22 de febrero, la API NO traerá bookmarks**. El servidor devolverá un error `429 (Rate Limited)`.

### Opciones:

1. **Upgrade a plan pagado** - Límites mayores en X API

## Inicio rápido

### 1. Configurar variables de entorno

```bash
# .env
CLIENT_ID=client_id_de_x
CLIENT_SECRET=client_secret_de_x
REDIRECT_URI=http://localhost:8000/auth/x/callback
```

### 2. Instalar dependencias

```bash
pip install fastapi uvicorn httpx python-dotenv
```

### 3. Ejecutar servidor

```bash
uvicorn main:app --reload
```

### 4. Acceder a la app

```
http://localhost:8000
```

## Flujo de uso

1. **Login** - Haz clic en "Iniciar sesión con X"
2. **Autoriza** - Confirma los permisos solicitados
3. **Explora** - Tus bookmarks se cargan automáticamente
4. **Filtra** - Busca, ordena y visualiza

## Características UI

- **Búsqueda instantánea** - Filtra en tiempo real
- **Ordenamiento** - Más recientes, antiguos, A-Z, Z-A
- **Vista compacta** - Optimizada para leer contenido
- **Estadísticas** - Contador de bookmarks
- **Responsive** - Funciona en desktop y tablet
- **Diseño minimalista** - Interfaz Apple-like sin fricciones

## Estructura de datos

Cada bookmark almacena:

```json
{
  "id": "tweet_id",
  "content": "texto del tweet",
  "created_at": "2025-02-03T10:30:00Z",
  "author_id": "user_id"
}
```

## Seguridad

- Tokens guardados localmente en SQLite (con refresh automático)
- PKCE para OAuth (protección contra ataques, la mas avanzada en X)
- Sesiones validadas en cada solicitud
- No para producción - agregar HTTPS y session middleware

## Debugging

Ver logs en terminal:

```
---- BOOKMARKS REQUEST ----
User ID: ****************
Max Results: 10
User found: ***********
API Response Status: 429
Rate limited (429)
```

## Notas

- Los tokens se actualizan automáticamente si expiran
- El caché evita solicitudes redundantes
- Los bookmarks se sincronizan bajo demanda (no en background)
- Sin límite de almacenamiento local (SQLite)

## Próximas mejoras

- [ ] Mejorar UX LogOut
- [ ] Etiquetas personalizadas
- [ ] Sincronización automática en background
- [ ] Dark mode

---

**Status**: MVP | **Última actualización**: 3 de febrero, 2026