import google.generativeai as genai
import os
import re
import json
import logging
import time
import markdown
from datetime import datetime
from dotenv import load_dotenv
from typing import Optional, Dict, Any

# --- Environment Setup ---
load_dotenv()

# --- Configuration Class ---
class TutorialConfig:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables.")

        self.model = os.getenv("DIRECT_GEMINI_MODEL", "models/gemini-1.0-pro")

        self.settings = {
            'target_language': os.getenv("TARGET_LANGUAGE", "Polish"),
            'difficulty_level': os.getenv("DIFFICULTY_LEVEL", "intermediate"),
            'max_retries': int(os.getenv("MAX_API_RETRIES", 5)),
            'base_delay': int(os.getenv("API_CALL_DELAY", 30)),
            'output_dir': os.getenv("OUTPUT_DIR", "Generated_Tutors"),
            'topics_file': os.getenv("TOPICS_FILE", "topics.txt"),
            'cache_file': os.getenv("CACHE_FILE", "api_cache.json"),
            'safety_settings': {
                'harassment': 'block_medium_and_above',
                'hate': 'block_medium_and_above',
                'sex': 'block_medium_and_above',
                'danger': 'block_medium_and_above'
            },
            'include_python_examples': False,  # Add this option
        }

# --- Initialize Configuration ---
config = TutorialConfig()
genai.configure(api_key=config.api_key)

# --- Enhanced Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tutorial_generator.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# --- Model Selection Function ---
def choose_model():
    available_models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            available_models.append(m)

    if not available_models:
        logging.error("No generative models found.")
        return None

    print("Available Gemini Models:")
    for i, m in enumerate(available_models):
        print(f"{i + 1}. {m.name} ({m.display_name})")

    while True:
        try:
            choice = int(input("Enter the number of the model you want to use: "))
            if 1 <= choice <= len(available_models):
                return available_models[choice - 1].name
            else:
                print("Invalid choice.")
        except ValueError:
            print("Invalid input.")

# --- Caching ---
class APICache:
    def __init__(self, cache_file):
        self.cache_file = cache_file
        self.cache = self.load_cache()

    def load_cache(self):
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_cache(self):
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=4)
        except Exception as e:
            logging.error(f"Failed to save cache: {e}")

    def get(self, key):
        return self.cache.get(key)

    def set(self, key, value):
        self.cache[key] = value
        self.save_cache()

api_cache = APICache(config.settings['cache_file'])

# --- Helper Functions ---
def clean_json_response(text: str) -> str:
    patterns = [
        r'(?s)^.*?({.*}).*?$',
        r'^[^{]*({.*})[^}]*$',
        r'```json(.*?)```',
        r'```(.*?)```'
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return text.strip()

def safe_api_call(model, prompt: str, max_retries: int = config.settings['max_retries']) -> Optional[str]:
    cache_key = f"{model.model_name}:{prompt}"
    cached_response = api_cache.get(cache_key)
    if cached_response:
        logging.info(f"Using cached response for prompt: {prompt[:50]}...")
        return cached_response

    retry_count = 0
    while retry_count <= max_retries:
        try:
            response = model.generate_content(prompt)
            response_text = response.text
            api_cache.set(cache_key, response_text)
            return response_text
        except Exception as e:
            if '429' in str(e) or 'quota' in str(e).lower():
                delay = config.settings['base_delay'] * (2 ** retry_count)
                logging.warning(f"Rate limited. Waiting {delay} seconds...")
                time.sleep(delay)
                retry_count += 1
            else:
                logging.error(f"API Error: {str(e)}")
                return None
    logging.error("Max retries exceeded")
    return None

# --- System Prompt (for setting the overall tone) ---
SYSTEM_PROMPT = f"""
Jesteś doświadczonym nauczycielem programowania specjalizującym się w tworzeniu
zrozumiałych i angażujących tutoriali dla osób na poziomie średniozaawansowanym.
Twoje wyjaśnienia są zwięzłe, precyzyjne i oparte na praktycznych przykładach.
Używasz języka {config.settings['target_language']} i dostosowujesz styl do poziomu
{config.settings['difficulty_level']}.
Zawsze zwracaj treść w formacie Markdown.
"""

# --- Content Generation Functions (Modular and Refined) ---

def generate_definition(topic: str, section_title: str, detail_level: str) -> Optional[str]:
    """Generates a concise definition for a concept."""
    prompt = f"""
{SYSTEM_PROMPT}

Zdefiniuj krótko i precyzyjnie pojęcie: "{section_title}" w kontekście tematu "{topic}".
Poziom szczegółowości: {detail_level}.
"""
    return safe_api_call(tutorial_model, prompt)

def generate_java_code_example(topic: str, section_title: str, detail_level: str, context: str = "") -> Optional[str]:
    """Generates a Java code example."""
    prompt = f"""
{SYSTEM_PROMPT}

Wygeneruj *krótki* i *ilustrujący* przykład kodu w Java, który demonstruje pojęcie: "{section_title}"
w kontekście tematu "{topic}".  Dodaj komentarze do kodu. Poziom szczegółowości: {detail_level}.
{context}

Zwróć TYLKO blok kodu w Markdown (```java ... ```).
"""
    return safe_api_call(tutorial_model, prompt)

def generate_common_pitfalls(topic: str, section_title: str, detail_level: str) -> Optional[str]:
    prompt = f"""
{SYSTEM_PROMPT}
Wygeneruj listę 1-3 *typowych błędów* (common pitfalls) związanych z "{section_title}" w temacie "{topic}".
Poziom szczegółowości: {detail_level}.
Dla każdego błędu:
* Krótki opis.
* Przykład *błędnego* kodu w Java (w bloku kodu Markdown).
* Wyjaśnienie, dlaczego to jest błąd.
* Wskazówki, jak uniknąć.

Format: lista wypunktowana Markdown.
"""
    return safe_api_call(tutorial_model, prompt)

def generate_best_practices(topic: str, section_title: str, detail_level: str) -> Optional[str]:
    prompt = f"""
{SYSTEM_PROMPT}

Wygeneruj listę 1-3 *najlepszych praktyk* związanych z "{section_title}" w temacie "{topic}".
Poziom szczegółowości: {detail_level}.
Każda praktyka powinna być:
* Konkretna.
* Uzasadniona.

Format: lista wypunktowana Markdown.
"""
    return safe_api_call(tutorial_model, prompt)

def generate_analogy(topic: str, section_title: str, detail_level: str) -> Optional[str]:
    """Generates an analogy to explain a concept."""
    if detail_level == "low":
        return None # No analogies for low detail

    prompt = f"""
{SYSTEM_PROMPT}

Podaj *krótką* analogię z życia codziennego, która pomoże zrozumieć pojęcie: "{section_title}"
w kontekście tematu "{topic}".
"""
    return safe_api_call(tutorial_model, prompt)

def generate_assessments(topic: str, detail_level: str) -> Optional[str]:
    """Generates assessments in Markdown format."""
    prompt = f"""
{SYSTEM_PROMPT}

Wygeneruj propozycje oceniania (assessments) dla tutorialu o temacie "{topic}".
Poziom szczegółowości: {detail_level}.

* Przykłady zadań formatywnych (sprawdzenie zrozumienia w trakcie).
* Przykłady zadań sumatywnych (ocena opanowania po tutorialu).

Format: Markdown.
"""
    return safe_api_call(tutorial_model, prompt)


def generate_tutorial_structure(topic: str, detail_level: str) -> Optional[Dict[str, Any]]:
    duration_map = {
        "low": 15,
        "medium": 45,
        "high": 90,
        "ultra": 180
    }
    total_duration = duration_map.get(detail_level, 45)

    prompt = f"""
{SYSTEM_PROMPT}

[IMPORTANT] Respond ONLY with valid JSON.

Stwórz strukturę tutorialu na temat: "{topic}".
Język: {config.settings['target_language']}.
Poziom szczegółowości: {detail_level}.
Całkowity czas: {total_duration} minut.

Struktura (JSON):
{{
    "metadata": {{
        "topic": "{topic}",
        "created": "{datetime.now().isoformat()}",
        "version": "1.0",
        "detail_level": "{detail_level}"
    }},
    "sections": [
        {{
            "title": "Tytuł sekcji 1",
            "duration": 15,
            "type": "introduction",
            "key_points": ["Punkt 1", "Punkt 2"]
        }},
        {{
            "title": "Tytuł sekcji 2",
            "duration": 25,
            "type": "theory",
            "key_points": ["Punkt 3", "Punkt 4"]
        }}
    ],
    "assessments": {{
        "formative": ["Pytanie 1", "Pytanie 2"],
        "summative": "Quiz"
    }}
}}

Zasady:
* Suma czasów sekcji = {total_duration}.
* Różne typy sekcji ("introduction", "theory", "practice", "discussion", "summary").
* Kluczowe punkty ("key_points") dla każdej sekcji.
* TYLKO poprawny JSON.
"""

    raw_text = safe_api_call(tutorial_model, prompt)
    if not raw_text:
        return None

    try:
        cleaned_text = clean_json_response(raw_text)
        parsed_json = json.loads(cleaned_text)
        sections = parsed_json.get('sections', [])
        num_sections = len(sections)
        if num_sections > 0:
            duration_per_section = total_duration // num_sections
            remainder = total_duration % num_sections
            for i, section in enumerate(sections):
                section['duration'] = duration_per_section + (1 if i < remainder else 0)
        return parsed_json
    except json.JSONDecodeError as e:
        logging.error(f"JSON parsing failed (structure): {e}")
        return None

class TutorialGenerator:
    def __init__(self):
        self.tutorial_data = {}

    def generate_full_tutorial(self, topic: str, detail_level: str) -> Optional[str]:
        """Generates the full tutorial content and converts it to HTML."""
        try:
            self.tutorial_data = generate_tutorial_structure(topic, detail_level)
            if not self.tutorial_data:
                return None

            for section in self.tutorial_data.get('sections', []):
                section_title = section['title']
                duration = section['duration']
                key_points = section.get('key_points', [])

                # Iterative generation for each section part
                definition = generate_definition(topic, section_title, detail_level)
                if definition:
                    section['definition'] = definition

                context = f"Właśnie zdefiniowaliśmy: {definition}\n" if definition else ""
                code_example = generate_java_code_example(topic, section_title, detail_level, context)
                if code_example:
                    section['code_example'] = code_example

                analogy = generate_analogy(topic, section_title, detail_level)
                if analogy:
                    section['analogy'] = analogy

                pitfalls = generate_common_pitfalls(topic, section_title, detail_level)
                if pitfalls:
                    section['common_pitfalls'] = pitfalls

                best_practices = generate_best_practices(topic, section_title, detail_level)
                if best_practices:
                    section['best_practices'] = best_practices


            if 'assessments' in self.tutorial_data:
                assessments_md = generate_assessments(topic, detail_level)
                if assessments_md:
                    self.tutorial_data['assessments'] = assessments_md


            markdown_output = self._format_to_markdown()
            html_output = self._convert_md_to_html(markdown_output)
            return html_output

        except Exception as e:
            logging.error(f"Critical failure: {e}")
            return None

    def _format_to_markdown(self) -> str:
        md_content = f"# {self.tutorial_data['metadata']['topic']}\n\n"
        md_content += f"**Created**: {self.tutorial_data['metadata']['created']}\n"
        md_content += f"**Level**: {config.settings['difficulty_level'].title()}\n"
        md_content += f"**Detail Level**: {self.tutorial_data['metadata']['detail_level'].title()}\n\n"

        for section in self.tutorial_data.get('sections', []):
            md_content += f"## {section['title']} ({section['duration']} minutes)\n\n"

            if 'definition' in section:
                md_content += "**Definicja:**\n" + section['definition'] + "\n\n"
            if 'code_example' in section:
                md_content += "**Przykład kodu:**\n" + section['code_example'] + "\n\n"
            if 'analogy' in section:
                md_content += "**Analogia:**\n" + section['analogy'] + "\n\n"
            if 'common_pitfalls' in section:
                md_content += "**Typowe Pułapki:**\n" + section['common_pitfalls'] + "\n\n"
            if 'best_practices' in section:
                md_content += "**Najlepsze Praktyki:**\n" + section['best_practices'] + "\n\n"

        if 'assessments' in self.tutorial_data:
            md_content += "\n## Assessments\n\n" + self.tutorial_data['assessments']

        return md_content

    def _convert_md_to_html(self, md_content: str) -> str:
        html_content = markdown.markdown(md_content, extensions=['fenced_code', 'codehilite'])
        return f"""<!DOCTYPE html>
<html lang="{config.settings['target_language']}">
<head>
    <meta charset="UTF-8">
    <title>{self.tutorial_data['metadata']['topic']}</title>
    <style>
        body {{ font-family: sans-serif; line-height: 1.6; }}
        h1, h2, h3 {{ margin-bottom: 0.5em; }}
        pre {{ background-color: #f0f0f0; padding: 1em; overflow-x: auto; }}
        .codehilite .err {{ color: red; }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>"""

def read_topics_from_file(filepath: str) -> list[tuple[str, str]]:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        topics = []
        for line in lines:
            parts = line.split("/")
            topic = parts[0].strip()
            detail_level = "medium"
            if len(parts) > 1:
                detail_level_cmd = parts[-1].strip().lower()
                if detail_level_cmd in ["low", "medium", "high", "ultra"]:
                    detail_level = detail_level_cmd
            topics.append((topic, detail_level))
        return topics
    except FileNotFoundError:
        logging.error(f"File not found: {filepath}")
        return []

# --- Main Execution ---
if __name__ == "__main__":
    selected_model_name = choose_model()
    if not selected_model_name:
        exit()

    try:
        tutorial_model = genai.GenerativeModel(
            model_name=selected_model_name,
            safety_settings=config.settings['safety_settings']
        )
    except Exception as e:
        logging.error(f"Failed to initialize model: {e}")
        raise

    generator = TutorialGenerator()
    topics_file = config.settings['topics_file']
    output_dir = config.settings['output_dir']

    topics_with_levels = read_topics_from_file(topics_file)
    if not topics_with_levels:
        print("No topics found.")
        exit()

    os.makedirs(output_dir, exist_ok=True)

    for topic, detail_level in topics_with_levels:
        logging.info(f"Generating: {topic}, Level: {detail_level}")
        html_tutorial = generator.generate_full_tutorial(topic, detail_level)

        if html_tutorial:
            filename = f"tutorial_{topic.replace(' ', '_').replace('/', '_')}_{detail_level}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            filepath = os.path.join(output_dir, filename)
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(html_tutorial)
                logging.info(f"Saved to {filepath}")
            except Exception as e:
                logging.error(f"Failed to save: {e}")
        else:
            logging.error(f"Generation failed for: {topic}")

    print("Generation complete.")