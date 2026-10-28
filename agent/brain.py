import json
import os
import time
import urllib.request
import urllib.error


# ==========================================================
# CONSTANTES GLOBALES
# ==========================================================
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_VERSION_URL = "http://localhost:11434/api/version"
OMNIROUTE_URL = "http://localhost:20128/v1/chat/completions"
OMNIROUTE_HEALTH_URL = "http://127.0.0.1:20128/api/monitoring/health"
OMNIROUTE_API_KEY = os.environ.get("OMNIROUTE_API_KEY", "")
OMNIROUTE_MODEL = os.environ.get("OMNIROUTE_MODEL", "nvidia/llama-3.1-70b-instruct")
OLLAMA_FAST = "llama3.2:3b"
OLLAMA_HEAVY = "qwen2.5:7b"
OLLAMA_FALLBACK = "qwen2.5:3b"
REQUEST_TIMEOUT = 120
KEEP_ALIVE = "30m"


# ==========================================================
# CATEGORIAS DE TAREA (clase plana, compatibilidad total)
# ==========================================================

class TaskCategory:
    """Categorias semanticas para routing de modelos."""
    UNKNOWN = "unknown"
    CODING = "coding"
    REASONING = "reasoning"
    CREATIVE = "creative"
    ANALYSIS = "analysis"
    CONVERSATIONAL = "conversational"
    AUTOMATION = "automation"
    FLASH = "flash"

    @classmethod
    def detect(cls, query: str) -> str:
        """Detecta la categoria semantica de la consulta del usuario."""
        if not query:
            return cls.UNKNOWN
        q = query.lower()
        # FLASH: saludos, hora, fecha
        flash_keys = {"hola", "buenos", "gracias", "adios", "que hora", "fecha", "como estas"}
        if any(k in q for k in flash_keys):
            return cls.FLASH

        # Sets de_keys definidos localmente para evitar choques
        _coding_keys = {"programa", "codigo", "refactor", "debug", "algoritmo",
                       "funcion", "function", "script", "clase", "clases", "desarrollo"}
        _reasoning_keys = {"analiza", "explica", "disena", "arquitectura", "complejo",
                          "investiga", "determina", "prueba", "resuelve", " paso a paso"}
        _creative_keys = {"escribe", "cuenta", "historia", "poema", "ideas", "prompt",
                         "creativo", "diseno", "dibuja"}
        _analysis_keys = {"resume", "compara", "diferencia", "estadistica", "datos",
                         "metric", "kpi", "report", "dashboard"}
        _automation_keys = {"ejecuta", "comando", "abre", "corre", "run", "write_file",
                           "remember", "plan_day"}

        counts = {
            cls.CODING: sum(1 for k in _coding_keys if k in q),
            cls.REASONING: sum(1 for k in _reasoning_keys if k in q),
            cls.CREATIVE: sum(1 for k in _creative_keys if k in q),
            cls.ANALYSIS: sum(1 for k in _analysis_keys if k in q),
            cls.AUTOMATION: sum(1 for k in _automation_keys if k in q),
            cls.FLASH: 0,  # Ya manejado arriba
        }
        best = max(counts, key=counts.get)
        if counts[best] == 0:
            return cls.CONVERSATIONAL  # Default para consultas no clasificadas
        return best


# ==========================================================
# TIERS DE MODELO (de mejor a peor calidad/precio)
# ==========================================================

class ModelTier:
    """Tiers de modelo ordenados de mayor a menor capacidad."""
    TIER_0_NVIDIA = "tier_0_nvidia"
    TIER_1_OLLAMA_HEAVY = "tier_1_ollaheavy"
    TIER_2_OLLAMA_FAST = "tier_2_ollafast"
    TIER_3_OLLAMA_FALLBACK = "tier_3_ollamafallback"


# ==========================================================
# CONFIGURACION OPTIMA DE MODELOS: (Tier, Categoria) -> modelo
# ==========================================================

_OPTIMAL_MODELS = {
    # Tier 0: NVIDIA via OmniRoute
    (ModelTier.TIER_0_NVIDIA, TaskCategory.CODING): "nvidia/codestral-22b-instruct",
    (ModelTier.TIER_0_NVIDIA, TaskCategory.REASONING): "nvidia/llama-3.1-70b-instruct",
    (ModelTier.TIER_0_NVIDIA, TaskCategory.CREATIVE): "nvidia/llama-3.1-70b-instruct",
    (ModelTier.TIER_0_NVIDIA, TaskCategory.ANALYSIS): "nvidia/llama-3.1-70b-instruct",
    (ModelTier.TIER_0_NVIDIA, TaskCategory.CONVERSATIONAL): "nvidia/llama-3.1-70b-instruct",
    (ModelTier.TIER_0_NVIDIA, TaskCategory.AUTOMATION): "nvidia/llama-3.1-70b-instruct",
    (ModelTier.TIER_0_NVIDIA, TaskCategory.FLASH): "nvidia/llama-3.1-70b-instruct",
    # Tier 1: Ollama heavy
    (ModelTier.TIER_1_OLLAMA_HEAVY, TaskCategory.CODING): OLLAMA_HEAVY,
    (ModelTier.TIER_1_OLLAMA_HEAVY, TaskCategory.REASONING): OLLAMA_HEAVY,
    (ModelTier.TIER_1_OLLAMA_HEAVY, TaskCategory.CREATIVE): OLLAMA_HEAVY,
    (ModelTier.TIER_1_OLLAMA_HEAVY, TaskCategory.ANALYSIS): OLLAMA_HEAVY,
    (ModelTier.TIER_1_OLLAMA_HEAVY, TaskCategory.CONVERSATIONAL): OLLAMA_HEAVY,
    (ModelTier.TIER_1_OLLAMA_HEAVY, TaskCategory.AUTOMATION): OLLAMA_HEAVY,
    # Tier 2: Ollama fast
    (ModelTier.TIER_2_OLLAMA_FAST, TaskCategory.CODING): OLLAMA_FAST,
    (ModelTier.TIER_2_OLLAMA_FAST, TaskCategory.CONVERSATIONAL): OLLAMA_FAST,
    (ModelTier.TIER_2_OLLAMA_FAST, TaskCategory.FLASH): OLLAMA_FAST,
    # Tier 3 fallback
    (ModelTier.TIER_3_OLLAMA_FALLBACK, TaskCategory.CONVERSATIONAL): OLLAMA_FALLBACK,
    (ModelTier.TIER_3_OLLAMA_FALLBACK, TaskCategory.FLASH): OLLAMA_FALLBACK,
    (ModelTier.TIER_3_OLLAMA_FALLBACK, TaskCategory.CODING): OLLAMA_FALLBACK,
    (ModelTier.TIER_3_OLLAMA_FALLBACK, TaskCategory.REASONING): OLLAMA_FALLBACK,
    (ModelTier.TIER_3_OLLAMA_FALLBACK, TaskCategory.CREATIVE): OLLAMA_FALLBACK,
    (ModelTier.TIER_3_OLLAMA_FALLBACK, TaskCategory.ANALYSIS): OLLAMA_FALLBACK,
    (ModelTier.TIER_3_OLLAMA_FALLBACK, TaskCategory.AUTOMATION): OLLAMA_FALLBACK,
}


# ==========================================================
# SCORING DE MODELOS Y POTENCIA
# ==========================================================

def _model_score(tier_val, category_val, omniroute_up, ollama_up):
    """Devuelve un score base por tier + ajuste por categoria y disponibilidad."""
    base = {
        ModelTier.TIER_0_NVIDIA: 30,
        ModelTier.TIER_1_OLLAMA_HEAVY: 25,
        ModelTier.TIER_2_OLLAMA_FAST: 20,
        ModelTier.TIER_3_OLLAMA_FALLBACK: 10,
    }
    score = base.get(tier_val, 10)

    # Bono por coincidencia de categoria
    category_bonus = {
        (ModelTier.TIER_0_NVIDIA, TaskCategory.CODING): 5,
        (ModelTier.TIER_0_NVIDIA, TaskCategory.REASONING): 5,
        (ModelTier.TIER_0_NVIDIA, TaskCategory.CREATIVE): 3,
        (ModelTier.TIER_0_NVIDIA, TaskCategory.ANALYSIS): 4,
        (ModelTier.TIER_1_OLLAMA_HEAVY, TaskCategory.REASONING): 4,
        (ModelTier.TIER_1_OLLAMA_HEAVY, TaskCategory.ANALYSIS): 3,
        (ModelTier.TIER_1_OLLAMA_HEAVY, TaskCategory.CODING): 3,
        (ModelTier.TIER_2_OLLAMA_FAST, TaskCategory.CONVERSATIONAL): 3,
        (ModelTier.TIER_2_OLLAMA_FAST, TaskCategory.FLASH): 3,
        (ModelTier.TIER_2_OLLAMA_FAST, TaskCategory.CODING): 2,
    }
    if (tier_val, category_val) in category_bonus:
        score += category_bonus[(tier_val, category_val)]

    # Penalizacion si el provider no esta disponible
    if tier_val == ModelTier.TIER_0_NVIDIA and not omniroute_up:
        score -= 20
    if tier_val in (ModelTier.TIER_1_OLLAMA_HEAVY, ModelTier.TIER_2_OLLAMA_FAST) and not ollama_up:
        score -= 10

    return max(score, 5)


def _compute_power_score(tier_val, category_val, omniroute_up, ollama_up,
                         gpu_available=None, memories_count=0):
    """Computa el score de poder (0-100) que refleja calidad esperada."""
    base_scores = {
        ModelTier.TIER_0_NVIDIA: 35,
        ModelTier.TIER_1_OLLAMA_HEAVY: 30,
        ModelTier.TIER_2_OLLAMA_FAST: 25,
        ModelTier.TIER_3_OLLAMA_FALLBACK: 15,
    }
    score = base_scores.get(tier_val, 15)

    # Bonos por coincidencia de categoria
    cat_bonus = {
        TaskCategory.CODING: 5,
        TaskCategory.REASONING: 5,
        TaskCategory.CREATIVE: 3,
        TaskCategory.ANALYSIS: 4,
        TaskCategory.CONVERSATIONAL: 2,
        TaskCategory.AUTOMATION: 3,
        TaskCategory.FLASH: 1,
    }
    score += cat_bonus.get(category_val, 0)

    # GPU bonus
    if gpu_available:
        util = gpu_available.get("util", 0)
        free_ratio = (100 - util) / 100
        score += int(10 * free_ratio)

    # Memorias bonus
    score += min(5, memories_count * 1)

    # Penalizaciones
    if not ollama_up and tier_val != ModelTier.TIER_3_OLLAMA_FALLBACK:
        score -= 5
    if not omniroute_up and tier_val == ModelTier.TIER_0_NVIDIA:
        score -= 15

    return max(min(score, 100), 0)


# ==========================================================
# DETECCION DE PALABRAS CLAVE Y _is_heavy (compatibilidad absoluta)
# ==========================================================

HEAVY_KEYWORDS = (
    "automejora", "mejora", "programa", "codigo", "escribe",
    "refactor", "debug", "error", "complejo", "analiza", "explica",
    "disena", "arquitectura", "base de datos", "api", "algoritmo",
    "investiga a fondo", "explica", "detalle", "paso a paso",
)


def _is_heavy(query):
    """Determina si la tarea requiere modelo pesado (heuristica vieja)."""
    q = query.lower() if query else ""
    return any(k in q for k in HEAVY_KEYWORDS)


def _detect_category(query):
    """Funcion independiente de deteccion de categoria (compatibilidad)."""
    return TaskCategory.detect(query)


# ==========================================================
# CACHE PARA DISPONIBILIDAD DE PROVIDERS
# ==========================================================

_AVAIL_CACHE = {"ollama": (0.0, False), "omniroute": (0.0, False)}
LAST_MODEL = None
LAST_PROVIDER = None
LAST_TIER = None
LAST_CATEGORY = None
LAST_SCORE = None
_AVAIL_TTL = 10.0


# ==========================================================
# FUNCIONES DE DISPONIBILIDAD
# ==========================================================

def _available(url, key):
    """Verifica si un endpoint esta disponible."""
    now = time.time()
    ts, val = _AVAIL_CACHE.get(key, (0.0, False))
    if now - ts < _AVAIL_TTL:
        return val
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            val = resp.status < 500
    except (urllib.error.URLError, OSError, Exception):
        val = False
    _AVAIL_CACHE[key] = (now, val)
    return val


def _available_ollama():
    """Verifica si Ollama esta arriba."""
    return _available(OLLAMA_VERSION_URL, "ollama")


def _available_omniroute():
    """Verifica si OmniRoute esta arriba."""
    return _available(OMNIROUTE_HEALTH_URL, "omniroute")


def _check_providers():
    """Chequea el estado de ambos providers."""
    return {
        "ollama": _available_ollama(),
        "omniroute": _available_omniroute(),
    }


# ==========================================================
# RUTING INTELIGENTE: seleccion del mejor modelo disponible
# ==========================================================

def _select_best_model(category, omniroute_up, ollama_up,
                       ollama_heavy_loaded=None, ollama_fast_loaded=None):
    """
    Selecciona el mejor modelo disponible para la categoria dada.
    Devuelve: (tier_str, modelo_nombre, score_potencia)
    """
    # Intentar Tier 0: NVIDIA via OmniRoute
    if omniroute_up and OMNIROUTE_API_KEY:
        tier = ModelTier.TIER_0_NVIDIA
        model = _OPTIMAL_MODELS.get((tier, category))
        if model:
            score = _model_score(tier, category, omniroute_up, ollama_up)
            return tier, model, score

    # Intentar Tier 1: Ollama heavy
    if ollama_up:
        heavy_names = ollama_heavy_loaded or []
        has_heavy = any("7b" in n or "qwen2.5" in n for n in heavy_names) if heavy_names else True
        if has_heavy:
            tier = ModelTier.TIER_1_OLLAMA_HEAVY
            model = _OPTIMAL_MODELS.get((tier, category))
            if not model:
                model = OLLAMA_HEAVY
            score = _model_score(tier, category, omniroute_up, ollama_up)
            return tier, model, score

    # Intentar Tier 2: Ollama fast
    if ollama_up:
        tier = ModelTier.TIER_2_OLLAMA_FAST
        model = _OPTIMAL_MODELS.get((tier, category))
        if not model:
            model = OLLAMA_FAST
        score = _model_score(tier, category, omniroute_up, ollama_up)
        return tier, model, score

    # Tier 3: Fallback minimo (cuando todo lo demas falla)
    tier = ModelTier.TIER_3_OLLAMA_FALLBACK
    model = _OPTIMAL_MODELS.get((tier, category))
    if not model:
        model = OLLAMA_FALLBACK
    score = _model_score(tier, category, omniroute_up, ollama_up)
    return tier, model, score


# ==========================================================
# FUNCION NUEVA: generacion de subagentes
# ==========================================================

def _generate_subagents(task_description, context=None):
    """
    Decompose a complex task into subtasks and assign each to an optimal agent.
    Returns a list of agent configs.
    """
    q = task_description.lower() if task_description else ""
    subagents = []

    if any(k in q for k in {"programa", "codigo", "funcion", "api", "algoritmo",
                           "refactor", "debug", "script", "desarrollo"}):
        subagents.extend([
            {"role": "analyst", "tier": ModelTier.TIER_0_NVIDIA, "model": "nvidia/llama-3.1-70b-instruct",
             "task": "Analizar requirements y definir especificaciones tecnicas"},
            {"role": "developer", "tier": ModelTier.TIER_0_NVIDIA, "model": "nvidia/codestral-22b-instruct",
             "task": "Implementar la solucion codificada"},
            {"role": "qa_tester", "tier": ModelTier.TIER_1_OLLAMA_HEAVY, "model": OLLAMA_HEAVY,
             "task": "Crear casos de prueba y validar funcionamiento"},
        ])
    elif any(k in q for k in {"investiga", "research", "resume", "compara", "datos", "metric",
                               "report", "dashboard", "estadistica"}):
        subagents.extend([
            {"role": "researcher", "tier": ModelTier.TIER_0_NVIDIA, "model": "nvidia/llama-3.1-70b-instruct",
             "task": "Buscar informacion y fuentes relevantes"},
            {"role": "synthesizer", "tier": ModelTier.TIER_1_OLLAMA_HEAVY, "model": OLLAMA_HEAVY,
             "task": "Sintesis de hallazgos en resumen coherente"},
            {"role": "reporter", "tier": ModelTier.TIER_1_OLLAMA_HEAVY, "model": OLLAMA_HEAVY,
             "task": "Redactar reporte estructurado con conclusiones"},
        ])
    elif any(k in q for k in {"escribe", "historia", "poema", "creativo", "prompt", "ideas",
                               "diseno", "dibuja"}):
        subagents.extend([
            {"role": "ideator", "tier": ModelTier.TIER_0_NVIDIA, "model": "nvidia/llama-3.1-70b-instruct",
             "task": "Generar ideas creativas y conceptos centrales"},
            {"role": "drafter", "tier": ModelTier.TIER_0_NVIDIA, "model": "nvidia/llama-3.1-70b-instruct",
             "task": "Redactar version completa del contenido solicitado"},
            {"role": "editor", "tier": ModelTier.TIER_1_OLLAMA_HEAVY, "model": OLLAMA_HEAVY,
             "task": "Revisar, mejorar estilo y coherencia"},
        ])
    elif any(k in q for k in {"ejecuta", "comando", "abre", "corre", "run", "sistema",
                               "ejecutar", "write_file", "remember"}):
        subagents.extend([
            {"role": "planner", "tier": ModelTier.TIER_1_OLLAMA_HEAVY, "model": OLLAMA_HEAVY,
             "task": "Planear los pasos de ejecucion y verificar permisos"},
            {"role": "executor", "tier": ModelTier.TIER_2_OLLAMA_FAST, "model": OLLAMA_FAST,
             "task": "Ejecutar comandos o abrir aplicaciones solicitadas"},
        ])
    else:
        subagents.extend([
            {"role": "researcher", "tier": ModelTier.TIER_0_NVIDIA, "model": "nvidia/llama-3.1-70b-instruct",
             "task": "Investigar y reunir informacion sobre la solicitud"},
            {"role": "planner", "tier": ModelTier.TIER_1_OLLAMA_HEAVY, "model": OLLAMA_HEAVY,
             "task": "Planear el enfoque paso a paso recomendado"},
            {"role": "executor", "tier": ModelTier.TIER_2_OLLAMA_FAST, "model": OLLAMA_FAST,
             "task": "Ejecutar o guiar la ejecucion de la tarea planificada"},
        ])

    if context:
        for a in subagents:
            a["context"] = context

    return subagents


# ==========================================================
# FUNCIONES AUXILIARES
# ==========================================================

def _payload(messages, url, model, system_override=None, stream=True, max_tokens=1200, temperature=0.6):
    """Payload para enviar al modelo."""
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    if url == OLLAMA_URL:
        payload.pop("max_tokens", None)
        payload["keep_alive"] = KEEP_ALIVE
        payload["options"] = {"num_predict": max_tokens}
    if system_override:
        payload["messages"] = [{"role": "system", "content": system_override}] + messages
    return payload


def _post_stream(url, payload, timeout=None):
    """POST stream a la URL del modelo."""
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if url == OMNIROUTE_URL and OMNIROUTE_API_KEY:
        headers["Authorization"] = "Bearer " + OMNIROUTE_API_KEY
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    return urllib.request.urlopen(req, timeout=timeout or REQUEST_TIMEOUT)


def _post_with_retry(url, payload, max_retries=2):
    """POST con reintentos para manejar rate limiting (429)."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                time.sleep(0.5 * attempt)
            return _post_stream(url, payload)
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code == 429 and attempt < max_retries:
                continue
            if e.code in (401, 403, 404):
                raise
            if attempt >= max_retries:
                raise
        except (urllib.error.URLError, OSError) as e:
            last_error = e
            if attempt < max_retries:
                continue
            raise
    if last_error:
        raise last_error
    return None


def _parse_openai_chunks(raw):
    """Parsea chunks SSE de OpenAI format."""
    parts = []
    for line in raw.split("\n"):
        line = line.strip()
        if not line.startswith("data:"):
            continue
        chunk = line[5:].strip()
        if chunk == "[DONE]":
            continue
        try:
            obj = json.loads(chunk)
        except (json.JSONDecodeError, Exception):
            continue
        choices = obj.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        if delta.get("content"):
            parts.append(delta["content"])
        msg = choices[0].get("message") or {}
        if msg.get("content"):
            parts.append(msg["content"])
    return "".join(parts)


def _parse_openai_full(raw):
    """Parsea respuesta completa OpenAI."""
    if raw.startswith("data:"):
        return _parse_openai_chunks(raw)
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        return ""
    try:
        return obj["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return ""


def _parse_ollama(raw):
    """Parsea respuesta de Ollama (formato NDJSON)."""
    try:
        obj = json.loads(raw)
        return (obj.get("message") or {}).get("content", "")
    except (json.JSONDecodeError, Exception):
        return ""


def _sane(reply):
    """Valida que la respuesta no sea vacia o basura."""
    if not reply or not reply.strip():
        return False
    letters = sum(1 for c in reply if c.isalnum())
    if letters < 6:
        return False
    stripped = reply.strip(" .!?¡¿😊😀😂😉😎🥰.,:;'"-()[]{}/\|*")
    if not stripped:
        return False
    return True


def _set_last(model, provider, tier=None, category=None, score=None):
    """Registra que cerebro respondio (para el panel de potencia)."""
    global LAST_MODEL, LAST_PROVIDER, LAST_TIER, LAST_CATEGORY, LAST_SCORE
    LAST_MODEL = model
    LAST_PROVIDER = provider
    if tier is not None:
        LAST_TIER = tier
    if category is not None:
        LAST_CATEGORY = category
    if score is not None:
        LAST_SCORE = score


def _last_user(messages):
    """Obtiene el ultimo mensaje de usuario."""
    for m in reversed(messages):
        if m.get("role") == "user":
            content = m.get("content", "")
            if isinstance(content, str):
                return content
    return ""


def _call_model(url, model, messages, system_override=None, max_tokens=1200, temperature=0.6):
    """Llama a un modelo y devuelve la respuesta como string."""
    payload = _payload(messages, url, model, system_override, stream=False,
                       max_tokens=max_tokens, temperature=temperature)
    with _post_with_retry(url, payload) as resp:
        raw = resp.read().decode("utf-8", errors="replace").strip()

    if url == OLLAMA_URL:
        return _parse_ollama(raw)
    return _parse_openai_full(raw)


# ==========================================================
# FUNCIONES DE CHAT PRINCIPALES
# ==========================================================

def chat(messages, system_override=None):
    """
    Respuesta completa sin streaming, con fallback inteligente de modelo/proveedor.
    Usa el routing semantico para seleccionar el mejor modelo.
    """
    global LAST_MODEL, LAST_PROVIDER, LAST_TIER, LAST_CATEGORY, LAST_SCORE
    LAST_MODEL = None
    LAST_PROVIDER = None
    LAST_TIER = None
    LAST_CATEGORY = None
    LAST_SCORE = None

    # Detectar categoria
    try:
        ul = _last_user(messages)
        category = TaskCategory.detect(ul) if ul else TaskCategory.CONVERSATIONAL
    except Exception:
        category = TaskCategory.CONVERSATIONAL

    # Chequear estado de providers
    providers = _check_providers()
    omniroute_up = providers["omniroute"]
    ollama_up = providers["ollama"]

    # Seleccionar modelo optimo
    try:
        tier, model, score = _select_best_model(category, omniroute_up, ollama_up)
    except Exception:
        tier, model, score = ModelTier.TIER_3_OLLAMA_FALLBACK, OLLAMA_FALLBACK, 10

    # Determinar URL
    is_nvidia_model = model and str(model).startswith("nvidia/")
    url = OMNIROUTE_URL if is_nvidia_model else OLLAMA_URL

    # Intentar llamada principal
    reply = ""
    try:
        reply = _call_model(url, model, messages, system_override)
    except Exception:
        reply = ""

    # Si no hay respuesta sana, intentar fallback a Ollama heavy
    if not _sane(reply) and ollama_up and tier != ModelTier.TIER_3_OLLAMA_FALLBACK:
        try:
            reply = _call_model(OLLAMA_URL, OLLAMA_HEAVY, messages, system_override)
            if _sane(reply):
                _set_last(OLLAMA_HEAVY, "ollama", ModelTier.TIER_1_OLLAMA_HEAVY, category, 25)
                return reply
        except Exception:
            pass

    # Si sigue sin funcionar, intentar con modelo fallback
    if not _sane(reply) and ollama_up:
        try:
            reply = _call_model(OLLAMA_URL, OLLAMA_FALLBACK, messages, system_override)
            if _sane(reply):
                _set_last(OLLAMA_FALLBACK, "ollama", ModelTier.TIER_3_OLLAMA_FALLBACK, category, 10)
                return reply
        except Exception:
            pass

    if not _sane(reply):
        _set_last(model if model else "none", "omniroute" if is_nvidia_model else "ollama", tier, category, score)
        return "NIAVA: no he podido generar una respuesta coherente. Podria reformular su pregunta, senor?"

    _set_last(model, "omniroute" if is_nvidia_model else "ollama", tier, category, score)
    return reply


def chat_heavy(messages, system_override=None):
    """Respuesta forzada con el modelo mas capaz disponible."""
    global LAST_MODEL, LAST_PROVIDER, LAST_TIER, LAST_CATEGORY, LAST_SCORE
    LAST_MODEL = None
    LAST_PROVIDER = None
    LAST_TIER = None
    LAST_CATEGORY = None
    LAST_SCORE = None

    providers = _check_providers()
    omniroute_up = providers["omniroute"]
    ollama_up = providers["ollama"]

    # Preferir NVIDIA via OmniRoute si esta disponible y tiene API key
    if omniroute_up and OMNIROUTE_API_KEY:
        model = OMNIROUTE_MODEL
        try:
            reply = _call_model(OMNIROUTE_URL, model, messages, system_override, max_tokens=1500)
            if _sane(reply):
                _set_last(model, "omniroute", ModelTier.TIER_0_NVIDIA, "heavy", 35)
                return reply
        except Exception:
            pass

    # Fallback a Ollama heavy
    if ollama_up:
        try:
            reply = _call_model(OLLAMA_URL, OLLAMA_HEAVY, messages, system_override, max_tokens=1500)
            if _sane(reply):
                _set_last(OLLAMA_HEAVY, "ollama", ModelTier.TIER_1_OLLAMA_HEAVY, "heavy", 25)
                return reply
        except Exception:
            pass

    # Fallback a Ollama fast
    if ollama_up:
        try:
            reply = _call_model(OLLAMA_URL, OLLAMA_FAST, messages, system_override, max_tokens=1200)
            if _sane(reply):
                _set_last(OLLAMA_FAST, "ollama", ModelTier.TIER_2_OLLAMA_FAST, "heavy", 15)
                return reply
        except Exception:
            pass

    _set_last("none", "none", ModelTier.TIER_3_OLLAMA_FALLBACK, "heavy", 0)
    return "NIAVA: no he podido generar una respuesta coherente, senor."


def chat_stream(messages, system_override=None):
    """Genera deltas del modelo en streaming, con routing inteligente."""
    global LAST_MODEL, LAST_PROVIDER, LAST_TIER, LAST_CATEGORY, LAST_SCORE
    LAST_MODEL = None
    LAST_PROVIDER = None
    LAST_TIER = None
    LAST_CATEGORY = None
    LAST_SCORE = None

    # Detectar categoria
    try:
        ul = _last_user(messages)
        category = TaskCategory.detect(ul) if ul else TaskCategory.CONVERSATIONAL
    except Exception:
        category = TaskCategory.CONVERSATIONAL

    providers = _check_providers()
    omniroute_up = providers["omniroute"]
    ollama_up = providers["ollama"]

    try:
        tier, model, score = _select_best_model(category, omniroute_up, ollama_up)
    except Exception:
        model, tier, score = OLLAMA_FALLBACK, ModelTier.TIER_3_OLLAMA_FALLBACK, 10

    # Construir candidatos en orden de preferencia
    candidates = []
    if omniroute_up and OMNIROUTE_API_KEY and model and str(model).startswith("nvidia/"):
        candidates.append((OMNIROUTE_URL, model, "omniroute"))
    if ollama_up and tier != ModelTier.TIER_0_NVIDIA:
        candidates.append((OLLAMA_URL, OLLAMA_HEAVY, "ollama"))
    if ollama_up:
        candidates.append((OLLAMA_URL, OLLAMA_FAST, "ollama"))
    if ollama_up:
        candidates.append((OLLAMA_URL, OLLAMA_FALLBACK, "ollama"))

    yielded_any = False
    for url, m, prov in candidates:
        try:
            for delta in _iter_chat(messages, url, m, system_override):
                yielded_any = True
                yield ("token", delta)
            if yielded_any:
                _set_last(m, prov, tier, category, score)
                yield ("outcome", {"kind": "answer", "text": "", "model": m, "tier": tier,
                                   "provider": prov})
                return
        except Exception:
            continue

    yield ("outcome", {"kind": "answer", "text": "No hay modelos disponibles en este momento, senor.",
                     "model": "fallback", "tier": "3", "provider": "none"})


def _iter_chat(messages, url, model, system_override=None):
    """Genera deltas del modelo en streaming."""
    payload = _payload(messages, url, model, system_override, stream=True)
    with _post_with_retry(url, payload) as resp:
        if url == OLLAMA_URL:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, Exception):
                    continue
                msg = obj.get("message") or {}
                content = msg.get("content") or ""
                if content:
                    yield content
                if obj.get("done"):
                    return
        else:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    return
                try:
                    obj = json.loads(chunk)
                except (json.JSONDecodeError, Exception):
                    continue
                choices = obj.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                if delta.get("content"):
                    yield delta["content"]


# ==========================================================
# PUNTO DE ENTRADA PARA PRUEBAS DIRECTAS
# ==========================================================

if __name__ == "__main__":
    print("Sistema de routing semantico de NIAVA activado")
    print("Categorias:", [v for k, v in vars(TaskCategory).items() if not k.startswith("_") and isinstance(v, str)])
    print("Tiers:", [v for k, v in vars(ModelTier).items() if not k.startswith("_") and isinstance(v, str)])
    print()
    providers = _check_providers()
    print("Providers:", providers)
    print()
    print("Modelos optimos:")
    for t in ModelTier:
        for c in TaskCategory:
            m = _OPTIMAL_MODELS.get((t, c))
            if m:
                print("  " + t + " + " + c + ": " + m)