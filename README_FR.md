[![Python-3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://quantalogic.github.io/quantalogic/)

Salut ! Bienvenue dans **QuantaLogic**—votre boîte à outils cosmique pour créer des agents IA et des flux de travail qui brillent ! Que vous codiez à tout-va, automatisiez un processus métier, discutiez avec un assistant intelligent ou imaginiez quelque chose de fou, QuantaLogic est là pour que ça se réalise. Nous parlons de **grands modèles de langage (LLM)** fusionnés avec un ensemble d'outils stellaires, comprenant trois approches puissantes : le **framework ReAct** pour une résolution de problèmes dynamique, le nouveau et éblouissant **module Flow** pour une brillance structurée, et un **mode Chat** étincelant pour une magie conversationnelle avec des capacités d'appel d'outils.

Imaginez ceci : une CLI aussi simple qu'un claquement de doigts, une API Python qui est de la pure magie, et un framework qui s'étend des hacks rapides aux entreprises galactiques. Prêt à décoller ? Lançons-nous !

[Documentation complète](https://quantalogic.github.io/quantalogic/) | [Guide pratique](./docs/howto/howto.md)

![Démo vidéo](./examples/generated_tutorials/python/quantalogic_8s.gif)

---
[Version chinoise](./README_CN.md)
[Version française](./README_FR.md)
[Version allemande](./README_DE.md)

## Pourquoi QuantaLogic ?

Chez [QuantaLogic](https://www.quantalogic.app), nous avons repéré un trou noir : les modèles d'IA incroyables d'OpenAI, Anthropic et DeepSeek n'illuminaient pas complètement les tâches du monde réel. Notre mission ? Allumer cette étincelle ! Nous sommes là pour rendre l'IA générative un jeu d'enfant pour les développeurs, les entreprises et les rêveurs—transformant les idées en action, une solution brillante à la fois, que ce soit par la résolution de tâches, des flux de travail structurés ou une conversation naturelle.

> "L'IA devrait être votre copilote, pas un casse-tête. QuantaLogic rend cela possible—rapidement, amusant et sans crainte !"

---

## Caractéristiques principales

- **Framework ReAct** : Raisonnement + action = agents inarrêtables !
- **Module Flow** : Des flux de travail structurés qui coulent comme une rivière.
- **Mode Chat** : Brillance conversationnelle avec des pouvoirs d'appel d'outils.
- **Galaxie LLM** : Accédez à OpenAI, DeepSeek et plus encore via LiteLLM.
- **Outils sécurisés** : Sécurité alimentée par Docker pour le code et les fichiers.
- **Surveillance en direct** : Regardez le déroulement avec une interface web et SSE.
- **Magie de la mémoire** : Un contexte intelligent maintient les choses vives.
- **Prêt pour l'entreprise** : Logs, gestion des erreurs et validation—solide comme le roc.

---

## Table des matières

- [Pourquoi QuantaLogic ?](#pourquoi-quantalogic)
- [Caractéristiques principales](#caractéristiques-principales)
- [Installation](#installation)
- [Démarrage rapide](#démarrage-rapide)
- [Framework ReAct : Agents dynamiques](#react-framework-agents-dynamiques)
- [Module Flow : Flux de travail structurés](#flow-module-flux-de-travail-structurés)
  - 📘 **[Spécification DSL YAML du flux de travail](./quantalogic/flow/flow_yaml.md)** : Guide complet pour définir des flux de travail puissants et structurés à l'aide de notre langage spécifique au domaine
  - 📚 **[Documentation YAML du flux de travail](./quantalogic/flow/flow_yaml)** : Plongez dans la documentation officielle pour une compréhension plus approfondie de Flow YAML et de ses applications
- [Mode Chat : Puissance conversationnelle](#chat-mode-puissance-conversationnelle)
- [ReAct vs. Flow vs. Chat : Choisissez votre pouvoir](#react-vs-flow-vs-chat-choisissez-votre-pouvoir)
- [Utilisation de la CLI](#utilisation-de-la-cli)
- [Exemples qui suscitent la joie](#exemples-qui-suscitent-la-joie)
- [Composants principaux](#composants-principaux)
- [Développement avec QuantaLogic](#développement-avec-quantalogic)
- [Contribution](#contribution)
- [Licence](#licence)
- [Croissance du projet](#croissance-du-projet)
- [Clés API et configuration de l'environnement](#clés-api-et-configuration-de-lenvironnement)

---

## Installation

Faisons orbiter QuantaLogic autour de votre système—c'est aussi simple que 1-2-3 !

### Ce dont vous aurez besoin
- **Python 3.12+** : Le carburant de notre fusée.
- **Docker** (facultatif) : Verrouille l'exécution du code dans un pod sûr.

### Option 1 : pip—Rapide et simple
```bash
pip install quantalogic
```

### Option 2 : pipx—Poussière d'étoile isolée
```bash
pipx install quantalogic
```

### Option 3 : Source—Pour les explorateurs de l'espace
```bash
git clone https://github.com/quantalogic/quantalogic.git
cd quantalogic
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
poetry install
```
> **Conseil** : Pas de Poetry ? Obtenez-le avec `pip install poetry` et rejoignez l'équipe !

---

## Démarrage rapide

Prêt à voir la magie ? Voici votre rampe de lancement :

### CLI : Action instantanée
```bash
quantalogic task "Écrire une fonction Python pour les nombres de Fibonacci"
```
> Boum ! ReAct concocte une solution en quelques secondes.

### CLI : Mode Chat
```bash
quantalogic chat --persona "Vous êtes un explorateur spatial spirituel" "Parlez-moi de Mars avec une recherche"
```
> Le mode Chat s'engage, utilise des outils si nécessaire et fournit une réponse conversationnelle !

### Python : Agent ReAct
```python
from quantalogic import Agent

agent = Agent(model_name="deepseek/deepseek-chat")
result = agent.solve_task("Coder une fonction Fibonacci")
print(result)
# Output: "def fib(n): return [0, 1] if n <= 2 else fib(n-1) + [fib(n-1)[-1] + fib(n-1)[-2]]"
```

### Python : Mode Chat
```python
from quantalogic import Agent

agent = Agent(model_name="gpt-4o", chat_system_prompt="Vous êtes un guide amical")
response = agent.chat("Quel temps fait-il à Tokyo ?")
print(response)
# S'engage dans la conversation, appelant potentiellement un outil météo si configuré
```

### Exemple d'agent synchrone
```python
from quantalogic import Agent

# Créer un agent synchrone
agent = Agent(model_name="gpt-4o")

# Résoudre une tâche de manière synchrone
result = agent.solve_task(
    task="Écrire une fonction Python pour calculer les nombres de Fibonacci",
    max_iterations=10  # Facultatif : limiter les itérations
)

print(result)
```

### Exemple d'agent asynchrone 🌊
```python
import asyncio
from quantalogic import Agent

async def main():
    # Créer un agent asynchrone
    agent = Agent(model_name="gpt-4o")
    
    # Résoudre une tâche de manière asynchrone avec streaming
    result = await agent.async_solve_task(
        task="Écrire un script Python pour scraper les principaux dépôts GitHub",
        max_iterations=15,  # Facultatif : limiter les itérations
        streaming=True      # Facultatif : diffuser la réponse
    )
    
    print(result)

# Exécuter la fonction asynchrone
asyncio.run(main())
```

### Exemples de surveillance d'événements 🔍

#### Surveillance d'événements synchrone avec des outils financiers
```python
from quantalogic import Agent
from quantalogic.console_print_events import console_print_events
from quantalogic.console_print_token import console_print_token
from quantalogic.tools import (
    DuckDuckGoSearchTool, 
    TechnicalAnalysisTool, 
    YFinanceTool
)

# Créer un agent avec des outils liés à la finance
agent = Agent(
    model_name="gpt-4o",
    tools=[
        DuckDuckGoSearchTool(),  # Outil de recherche web
        TechnicalAnalysisTool(),  # Analyse technique des actions
        YFinanceTool()            # Récupération des données boursières
    ]
)

# Configurer des écouteurs d'événements complets
agent.event_emitter.on(
    event=[
        "task_complete",
        "task_think_start", 
        "task_think_end", 
        "tool_execution_start", 
        "tool_execution_end",
        "error_max_iterations_reached",
        "memory_full",
        "memory_compacted"
    ],
    listener=console_print_events
)

# Facultatif : Surveiller les jetons de streaming
agent.event_emitter.on(
    event=["stream_chunk"], 
    listener=console_print_token
)

# Exécuter une tâche d'analyse financière en plusieurs étapes
result = agent.solve_task(
    "1. Trouver les 3 meilleures actions technologiques pour le T3 2024 "
    "2. Récupérer les données boursières historiques pour chacune "
    "3. Calculer les moyennes mobiles à 50 et 200 jours "
    "4. Fournir une brève recommandation d'investissement",
    streaming=True  # Activer le streaming pour une sortie détaillée
)
print(result)
```

#### Surveillance d'événements asynchrone avec des outils financiers
```python
import asyncio
from quantalogic import Agent
from quantalogic.console_print_events import console_print_events
from quantalogic.console_print_token import console_print_token
from quantalogic.tools import (
    DuckDuckGoSearchTool, 
    TechnicalAnalysisTool, 
    YFinanceTool
)

async def main():
    # Créer un agent asynchrone avec des outils liés à la finance
    agent = Agent(
        model_name="gpt-4o",
        tools=[
            DuckDuckGoSearchTool(),  # Outil de recherche web
            TechnicalAnalysisTool(),  # Analyse technique des actions
            YFinanceTool()            # Récupération des données boursières
        ]
    )

    # Configurer des écouteurs d'événements complets
    agent.event_emitter.on(
        event=[
            "task_complete",
            "task_think_start", 
            "task_think_end", 
            "tool_execution_start", 
            "tool_execution_end",
            "error_max_iterations_reached",
            "memory_full",
            "memory_compacted"
        ],
        listener=console_print_events
    )

    # Facultatif : Surveiller les jetons de streaming
    agent.event_emitter.on(
        event=["stream_chunk"], 
        listener=console_print_token
    )

    # Exécuter une tâche d'analyse financière en plusieurs étapes de manière asynchrone
    result = await agent.async_solve_task(
        "1. Trouver les startups émergentes de la technologie IA "
        "2. Analyser leurs récentes levées de fonds "
        "3. Comparer le potentiel du marché et les indicateurs de croissance "
        "4. Fournir un rapport sur les tendances d'investissement",
        streaming=True  # Activer le streaming pour une sortie détaillée
    )
    print(result)

# Exécuter la fonction asynchrone
asyncio.run(main())
```

### Python : Flux de travail Flow
```python
from quantalogic.flow import Workflow, Nodes

@Nodes.define(output="greeting")
def greet(name: str) -> str:
    return f"Bonjour, {name} !"

workflow = Workflow("greet").build()
result = await workflow.run({"name": "Luna"})
print(result["greeting"])  # "Bonjour, Luna !"
```

---

## Framework ReAct : Agents dynamiques

Le **framework ReAct** est votre acolyte IA—pensez vite, agissez intelligemment. Il associe le raisonnement LLM à l'action alimentée par des outils, parfait pour les tâches qui ont besoin d'un peu d'improvisation.

### Comment ça roule
1. **Vous dites** : "Écris-moi un script."
2. **Il pense** : LLM trace la voie.
3. **Il agit** : Des outils comme `PythonTool` se mettent au travail.
4. **Il boucle** : Continue jusqu'à ce que ce soit terminé.

Regardez ça :

```mermaid
graph TD
    A[Vous: 'Écris un script'] --> B[Agent ReAct]
    B --> C{Raisonner avec LLM}
    C --> D[Appeler les outils]
    D --> E[Obtenir les résultats]
    E --> F{Tâche terminée ?}
    F -->|Non| C
    F -->|Oui| G[Fournir la réponse]
    G --> H[Vous : Heureux !]
    style A fill:#f9f,stroke:#333
    style H fill:#bbf,stroke:#333
```

### Exemple : Générateur de code
```bash
quantalogic task "Créer un script Python pour trier une liste"
```
> ReAct comprend, écrit le code et le remet—doux comme de la soie !

### Pourquoi c'est cool
Parfait pour coder, déboguer ou répondre à des questions folles à la volée.

---

## Module Flow : Flux de travail structurés

Le **module Flow** est votre architecte—construisant des flux de travail qui bourdonnent avec précision. Il s'agit de nœuds, de transitions et d'un rythme régulier, idéal pour les missions répétables.

🔍 **Vous voulez approfondir ?** Consultez notre [Spécification DSL YAML du flux de travail](./quantalogic/flow/flow_yaml.md), un guide détaillé qui vous explique comment définir des flux de travail puissants et structurés. Des configurations de nœuds de base à la logique de transition complexe, cette documentation est votre feuille de route pour maîtriser la conception de flux de travail avec QuantaLogic.

📚 **Pour une compréhension plus approfondie de Flow YAML et de ses applications, veuillez consulter la [Documentation YAML du flux de travail](https://quantalogic.github.io/quantalogic/flow/flow_yaml) officielle.**

La documentation YAML du flux de travail fournit un aperçu complet du langage Flow YAML, y compris sa syntaxe, ses fonctionnalités et ses meilleures pratiques. C'est une ressource précieuse pour tous ceux qui cherchent à créer des flux de travail complexes avec QuantaLogic.

De plus, la documentation YAML du flux de travail comprend un certain nombre d'exemples et de tutoriels pour vous aider à démarrer avec la création de vos propres flux de travail. Ces exemples couvrent un éventail de sujets, des flux de travail simples aux scénarios plus complexes, et sont conçus pour vous aider à comprendre comment utiliser Flow YAML pour créer des flux de travail puissants et flexibles.

### Les éléments constitutifs
- **Nœuds** : Tâches comme des fonctions ou des appels LLM.
- **Transitions** : Chemins avec des conditions facultatives.
- **Moteur** : Dirige le spectacle avec flair.
- **Observateurs** : Jetez un coup d'œil aux progrès avec des événements.

### Exemple : Tisseur d'histoires
```python
from quantalogic.flow import Workflow, Nodes

@Nodes.llm_node(model="openai/gpt-4o-mini", output="chapter")
async def write_chapter(ctx: dict) -> str:
    return f"Chapitre 1 : {ctx['theme']}"

workflow = (
    Workflow("write_chapter")
    .then("end", condition="lambda ctx: True")
    .add_observer(lambda e: print(f" {e.event_type}"))
)
engine = workflow.build()
result = await engine.run({"theme": "Cosmic Quest"})
print(result["chapter"])
```

### Exemple : Agent générateur d'histoires
```python
from typing import List
import anyio
from loguru import logger
from quantalogic.flow import Nodes, Workflow

# Définir les fonctions de nœud avec des décorateurs
@Nodes.validate_node(output="validation_result")
async def validate_input(genre: str, num_chapters: int) -> str:
    """Valider les paramètres d'entrée."""
    if not (1 <= num_chapters <= 20 and genre.lower() in ["science fiction", "fantasy", "mystery", "romance"]):
        raise ValueError("Entrée invalide : le genre doit être l'un des suivants : science-fiction, fantastique, mystère, romance")
    return "Entrée validée"

@Nodes.llm_node(
    model="gemini/gemini-2.0-flash",
    system_prompt="Vous êtes un écrivain créatif spécialisé dans les titres d'histoires.",
    prompt_template="Générez un titre créatif pour une histoire de {{ genre }}. Sortez uniquement le titre.",
    output="title",
)
async def generate_title(genre: str) -> str:
    """Générer un titre basé sur le genre (géré par llm_node)."""
    pass  # Logique gérée par le décorateur llm_node

@Nodes.define(output="manuscript")
async def compile_book(title: str, outline: str, chapters: List[str]) -> str:
    """Compiler le manuscrit complet à partir du titre, du plan et des chapitres."""
    return f"Titre : {title}\n\nPlan :\n{outline}\n\n" + "\n\n".join(
        f"Chapitre {i}:\n{chap}" for i, chap in enumerate(chapters, 1)
    )

# Définir le flux de travail avec une branchement conditionnel
workflow = (
    Workflow("validate_input")
    .then("generate_title")
    .then("generate_outline")
    .then("generate_chapter")
    .then("update_chapter_progress")
    .then("generate_chapter", condition=lambda ctx: ctx["completed_chapters"] < ctx["num_chapters"])
    .then("compile_book", condition=lambda ctx: ctx["completed_chapters"] >= ctx["num_chapters"])
    .then("quality_check")
    .then("end")
)

# Exécuter le flux de travail
async def main():
    initial_context = {
        "genre": "science fiction",
        "num_chapters": 3,
        "chapters": [],
        "completed_chapters": 0,
    }
    engine = workflow.build()
    result = await engine.run(initial_context)
```

Cet exemple démontre :
- Validation d'entrée avec `@Nodes.validate_node`
- Intégration LLM avec `@Nodes.llm_node`
- Traitement personnalisé avec `@Nodes.define`
- Branchement conditionnel pour la génération itérative de chapitres
- Gestion du contexte pour le suivi des progrès

L'exemple complet est disponible sur [examples/flow/story_generator/story_generator_agent.py](./examples/flow/story_generator/story_generator_agent.py).

### Flow visualisé
```mermaid
graph LR
    A[Début] --> B[ÉcrireChapitre]
    B -->|Condition : Vrai| C[Fin]
    subgraph ÉcrireChapitre
        D[Appeler LLM] --> E[Enregistrer le chapitre]
    end
    A -->|Observateur| F[Log : NODE_STARTED]
    B -->|Observateur| G[Log : NODE_COMPLETED]
    style A fill:#dfd,stroke:#333
    style C fill:#dfd,stroke:#333
    style B fill:#ffb,stroke:#333
```

### Exemple : Pipeline de données
```python
@Nodes.define(output="processed")
def clean_data( str) -> str:
    return data.strip().upper()

workflow = Workflow("clean_data").build()
result = await workflow.run({"data": " hello "})
print(result["processed"])  # "HELLO"
```

### Pourquoi c'est génial
Pensez aux pipelines de contenu, aux flux d'automatisation ou à toute tâche en plusieurs étapes qui a besoin d'ordre.

---

## Mode Chat : Puissance conversationnelle

Le **mode Chat** est votre compagnon conversationnel—engageant, flexible et connaisseur des outils. Construit sur la même base ReAct robuste, il vous permet de discuter naturellement avec une personne IA tout en intégrant de manière transparente les appels d'outils si nécessaire. Parfait pour les dialogues interactifs ou les requêtes rapides avec une touche d'utilité.

### Comment ça marche
1. **Vous discutez** : "Quel temps fait-il aujourd'hui ?"
2. **Il répond** : S'engage de manière conversationnelle, en décidant si un outil (comme une recherche météo) est nécessaire.
3. **Magie de l'outil** : Si nécessaire, il appelle des outils en utilisant le même système basé sur XML que ReAct, puis intègre les résultats dans la conversation.
4. **Continue** : Maintient le contexte pour une conversation fluide.

### Exemple : Chat CLI avec appel d'outil
```bash
quantalogic chat --persona "Vous êtes un guide de voyage utile" "Trouvez-moi des vols pour Paris"
```
> L'agent répond : "Recherche de vols pour Paris… Voici quelques options d'un outil de recherche : [détails du vol]. Puis-je vous aider avec autre chose ?"

### Exemple : Chat Python avec appel d'outil
```python
from quantalogic import Agent
from quantalogic.tools import DuckDuckGoSearchTool

agent = Agent(
    model_name="gpt-4o",
    chat_system_prompt="Vous êtes un explorateur curieux",
    tools=[DuckDuckGoSearchTool()]
)
response = agent.chat("Parlez-moi de la plus haute montagne")
print(response)
# Pourrait sortir : "Je vais vérifier ça ! La plus haute montagne est le mont Everest, culminant à 8 848 mètres, selon une recherche rapide."
```

### Intégration d'outils
Le mode Chat utilise le même mécanisme d'appel d'outils que ReAct :
```xml
<action>
<duckduckgo_tool>
  <query>plus haute montagne</query>
  <max_results>5</max_results>
</duckduckgo_tool>
</action>
```
- Les outils sont exécutés automatiquement (configurable avec `--auto-tool-call`) et les résultats sont formatés naturellement.
- Prioriser des outils spécifiques avec `--tool-mode` (par exemple, `search` ou `code`).

### Pourquoi c'est génial
Idéal pour les conversations décontractées, les recherches d'informations rapides ou l'assistance interactive avec une précision alimentée par des outils—sans la structure rigide de résolution de tâches de ReAct.

---

## ReAct vs. Flow vs. Chat : Choisissez votre pouvoir

Les trois modes sont stellaires, mais voici le scoop :

| Caractéristique        | Framework ReAct         | Module Flow             | Mode Chat               |
|------------------------|-------------------------|-------------------------|-------------------------|
| **Ambiance**          | Esprit libre, adaptatif | Organisé, prévisible  | Conversationnel, flexible |
| **Flux**            | Boucle jusqu'à ce que ce soit résolu | Suit une feuille de route | Flue avec le chat      |
| **Point fort**      | Chaos créatif (codage, Q&A) | Flux de travail réguliers (pipelines) | Conversations décontractées, requêtes rapides |
| **État**           | La mémoire le maintient lâche | Les nœuds le verrouillent | Le contexte le maintient fluide |
| **Outils**           | Saisi au besoin         | Intégré dans les nœuds | Appelé lorsque pertinent |
| **Regardez-le**      | Événements comme `task_complete` | Observateurs comme `NODE_STARTED` | Événements comme `chat_response` |

### Quand choisir
- **ReAct** : Code à la volée, explorez les réponses, déboguez comme un pro.
- **Flow** : Construisez un pipeline, automatisez un processus, gardez-le serré.
- **Chat** : Conversez naturellement, obtenez des réponses rapides, utilisez des outils à la demande.

---

## Utilisation de la CLI

La CLI est votre centre de commande—rapide, flexible et amusant !

### Syntaxe
```bash
quantalogic [OPTIONS] COMMANDE [ARGS]...
```

### Description
Assistant IA QuantaLogic - Un outil IA puissant pour diverses tâches.

### Variables d'environnement
- **OpenAI** : Définissez `OPENAI_API_KEY` sur votre clé API OpenAI
- **Anthropic** : Définissez `ANTHROPIC_API_KEY` sur votre clé API Anthropic
- **DeepSeek** : Définissez `DEEPSEEK_API_KEY` sur votre clé API DeepSeek

Utilisez un fichier `.env` ou exportez ces variables dans votre shell pour une intégration transparente.

### Commandes
- **`task`** : Lancez une mission.
  ```bash
  quantalogic task "Résumer ce fichier" --file notes.txt
  ```
- **`chat`** : Démarrez une conversation.
  ```bash
  quantalogic chat --persona "Vous êtes un gourou de la technologie" "Quoi de neuf dans l'IA ?"
  ```
- **`list-models`** : Répertorie les modèles LiteLLM pris en charge avec une recherche floue facultative.
  ```bash
  quantalogic list-models --search "gpt"
  ```

### Options
- **`--model-name TEXT`** : Spécifiez le modèle à utiliser (format litellm). Exemples :
  - `openai/gpt-4o-mini`
  - `openai/gpt-4o`
  - `anthropic/claude-3.5-sonnet`
  - `deepseek/deepseek-chat`
  - `deepseek/deepseek-reasoner`
  - `openrouter/deepseek/deepseek-r1`
  - `openrouter/openai/gpt-4o`
- **`--mode [code|basic|interpreter|full|code-basic|search|search-full|chat]`** : Mode agent
- **`--vision-model-name TEXT`** : Spécifiez le modèle de vision à utiliser (format litellm)
- **`--log [info|debug|warning]`** : Définir le niveau de journalisation
- **`--verbose`** : Activer la sortie détaillée
- **`--max-iterations INTEGER`** : Nombre maximal d'itérations (par défaut : 30, mode tâche uniquement)
- **`--max-tokens-working-memory INTEGER`** : Définir le nombre maximal de jetons autorisés dans la mémoire de travail
- **`--compact-every-n-iteration INTEGER`** : Définir la fréquence du compactage de la mémoire
- **`--thinking-model TEXT`** : Le modèle de pensée à utiliser
- **`--persona TEXT`** : Définir la personne du chat (mode chat uniquement)
- **`--tool-mode TEXT`** : Prioriser un outil ou un ensemble d'outils (mode chat uniquement)
- **`--auto-tool-call`** : Activer/désactiver l'exécution automatique des outils (mode chat uniquement, par défaut : True)
- **`--version`** : Afficher les informations sur la version

> **Conseil** : Exécutez `quantalogic --help` pour la référence de commande complète !

---

## Exemples qui suscitent la joie

Explorez notre collection d'exemples pour voir QuantaLogic en action :

- [Exemples de flux](./examples/flow/README.md) : Découvrez des flux de travail pratiques présentant les capacités de Quantalogic Flow
- [Exemples d'agents](./examples/agent/README.md) : Voyez des agents dynamiques en action avec le framework ReAct
- [Exemples d'outils](./examples/tools/README.md) : Explorez nos puissantes intégrations d'outils

Chaque exemple est livré avec une documentation détaillée et un code prêt à l'emploi.

### Magie vidéo
[![Démo du tutoriel](./examples/generated_tutorials/python/quantalogic_long.mp4)](./examples/generated_tutorials/python/quantalogic_long.mp4)

### Exemples pratiques
| Nom                  | Que fait-il ?                             | Fichier                                           |
|----------------------|------------------------------------------|-------------------------------------------------|
| Agent simple         | Démo d'agent ReAct de base                | [01-simple-agent.py](./examples/01-simple-agent.py) |
| Surveillance d'événements | Agent avec suivi des événements           | [02-agent-with-event-monitoring.py](./examples/02-agent-with-event-monitoring.py) |
| Mode interpréteur     | Agent avec interpréteur                  | [03-agent-with-interpreter.py](./examples/03-agent-with-interpreter.py) |
| Résumé de l'agent    | Génération de résumé de tâche             | [04-agent-summary-task.py](./examples/04-agent-summary-task.py) |
| Génération de code   | Génération de code de base               | [05-code.py](./examples/05-code.py) |
| Écran de code        | Génération de code avancée              | [06-code-screen.py](./examples/06-code-screen.py) |
| Écrivain de tutoriel  | Écrire des tutoriels techniques          | [07-write-tutorial.py](./examples/07-write-tutorial.py) |
| Écrivain PRD         | Document des exigences du produit        | [08-prd-writer.py](./examples/08-prd-writer.py) |
| Générateur d'histoires | Création d'histoires basée sur Flow        | [story_generator_agent.py](./examples/flow/story_generator/story_generator_agent.py) |
| Requête SQL          | Génération de requête de base de données | [09-sql-query.py](./examples/09-sql-query.py) |
| Agent financier      | Analyse financière et tâches             | [10-finance-agent.py](./examples/10-finance-agent.py) |
| Interface textuelle | Agent avec interface utilisateur textuelle | [11-textual-agent-interface.py](./examples/11-textual-agent-interface.py) |
| Test Composio        | Démo d'intégration Composio             | [12-composio-test.py](./examples/12-composio-test.py) |
| Agent synchrone      | Démo d'agent synchrone                | [13-synchronous-agent.py](./examples/13-synchronous-agent.py) |
| Agent asynchrone      | Démo d'agent asynchrone                  | [14-async-agent.py](./examples/14-async-agent.py) |

### Bonus : Génie des maths
```bash
quantalogic task "Résoudre 2x + 5 = 15"
```
> Sortie : "Résolvons ça ! 2x + 5 = 15 → 2x = 10 → x = 5. Terminé !"

### Bonus : Requête de chat
```bash
quantalogic chat "Rechercher les dernières percées de l'IA"
```
> Sortie : "Je vais creuser ça ! Voici ce que j'ai trouvé avec une recherche : [dernières nouvelles de l'IA]. Plutôt cool, non ?"

---

## Composants principaux

### Agents ReAct
- **Cerveau** : Les LLM alimentent la pensée.
- **Mains** : Des outils comme `PythonTool` font le travail.
- **Mémoire** : Relie tout ensemble.

### Flux de travail Flow
- **Nœuds** : Vos blocs de tâches.
- **Moteur** : Le maestro de l'exécution.

### Mode Chat
- **Personne** : Style conversationnel personnalisable.
- **Outils** : Intégrés de manière transparente via le système de ReAct.
- **Contexte** : Maintient la conversation fluide.

### Arsenal d'outils
- **Code** : `PythonTool`, `NodeJsTool`.
- **Fichiers** : `ReadFileTool`, `WriteFileTool`.
- Plus dans [REFERENCE_TOOLS.md](./REFERENCE_TOOLS.md).

---

## Développement avec QuantaLogic

### Configurez votre laboratoire
```bash
git clone https://github.com/quantalogic/quantalogic.git
cd quantalogic
python -m venv venv
source venv/bin/activate
poetry install
```

### Testez le cosmos
```bash
pytest --cov=quantalogic
```

### Peaufinez-le
```bash
ruff format  # Faites briller ce code
mypy quantalogic  # Vérifiez les types
ruff check quantalogic  # Linter-le
```

### Créer des outils personnalisés
La fonction `create_tool()` transforme n'importe quelle fonction Python en un outil réutilisable :

```python
from quantalogic.tools import create_tool

def weather_lookup(city: str, country: str = "US") -> dict:
    """Récupérer la météo actuelle pour un emplacement donné.
    
    Args:
        city: Nom de la ville à rechercher
        country: Code de pays à deux lettres (par défaut : US)
    
    Returns:
        Dictionnaire avec des informations météorologiques
    """
    # Implémenter la logique de recherche météo ici
    return {"temperature": 22, "condition": "Ensoleillé"}

# Convertir la fonction en un outil
weather_tool = create_tool(weather_lookup)

# Maintenant, vous pouvez l'utiliser comme un outil
print(weather_tool.to_markdown())  # Générer la documentation de l'outil
result = weather_tool.execute(city="New York")