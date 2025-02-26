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
class LessonConfig:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables.")

        self.models = {
            'structure': os.getenv("STRUCTURE_MODEL", "models/gemini-2.0-flash-thinking-exp-01-21"),
            'content': os.getenv("CONTENT_MODEL", "models/gemini-2.0-flash-thinking-exp-01-21"),
        }
        self.settings = {
            'target_language': os.getenv("TARGET_LANGUAGE", "Polish"),
            'difficulty_level': os.getenv("DIFFICULTY_LEVEL", "intermediate"),
            'lesson_length': int(os.getenv("LESSON_LENGTH", 90)),
            'max_retries': int(os.getenv("MAX_RETRIES", 3)),
            'base_delay': int(os.getenv("API_DELAY", 5)),  # Keep a reasonable delay
            'output_dir': os.getenv("OUTPUT_DIR", "generated_lessons"),
            'topics_file': os.getenv("TOPICS_FILE", "topics.txt"), # Path to the topics file
            'safety_settings': {
                'harassment': 'block_medium_and_above',
                'hate': 'block_medium_and_above',
                'sex': 'block_medium_and_above',
                'danger': 'block_medium_and_above'
            }
        }

# --- Initialize Configuration ---
config = LessonConfig()
genai.configure(api_key=config.api_key)

# --- Enhanced Logging ---
# Log to file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('lesson_generator.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# --- Model Initialization ---
try:
    structure_model = genai.GenerativeModel(
        model_name=config.models['structure'],
        safety_settings=config.settings['safety_settings']
    )

    content_model = genai.GenerativeModel(
        model_name=config.models['content'],
        safety_settings=config.settings['safety_settings']
    )

except Exception as e:
    logging.error(f"Failed to initialize models: {str(e)}")
    raise

# --- Helper Functions ---
def clean_json_response(text: str) -> str:
    """Cleans the JSON response, handling common issues."""
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
    """Makes an API call with retries and error handling."""
    retry_count = 0
    while retry_count <= max_retries:
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            if '429' in str(e) or 'quota' in str(e).lower():
                delay = config.settings['base_delay'] * (2 ** retry_count)
                logging.warning(f"Rate limited or quota exceeded. Waiting {delay} seconds...")
                time.sleep(delay)
                retry_count += 1
            else:
                logging.error(f"API Error: {str(e)}")
                return None
    logging.error("Max API retries exceeded")
    return None

# --- Content Generation Functions (Modular) ---

def generate_learning_objectives(topic: str, section_title: str, duration: int) -> Optional[str]:
    """Generates learning objectives for a section."""
    prompt = f"""
Jesteś doświadczonym nauczycielem programowania, specjalizującym się w tworzeniu materiałów edukacyjnych dla osób na poziomie średniozaawansowanym.

Twoim zadaniem jest wygenerowanie listy celów nauki (learning objectives) dla sekcji lekcji o nazwie "{section_title}".
Temat lekcji: {topic}
Czas trwania sekcji: {duration} minut
Poziom trudności: {config.settings['difficulty_level']}
Język: {config.settings['target_language']}

Cele nauki powinny być:
* Zwięzłe i precyzyjne.  Maksymalnie 2-3 zdania na cel.
* Mierzalne (co uczeń będzie potrafił *zrobić* po ukończeniu sekcji).  Używaj czasowników operacyjnych, np. "Zdefiniować...", "Wyjaśnić...", "Napisać...", "Zastosować...", "Rozróżnić...", "Zaprojektować...", "Zaimplementować...".
* Zaczynać się od czasownika w formie bezokolicznika.
* Być sformułowane w języku {config.settings['target_language']}.
* Być realistyczne do osiągnięcia w czasie {duration} minut.
* Bezpośrednio związane z tematem sekcji "{section_title}".

**Przykłady dobrych celów nauki (dla innej sekcji):**
* Zdefiniować pojęcie funkcji w Pythonie i wyjaśnić jej rolę w programowaniu.
* Napisać prostą funkcję w Pythonie, która przyjmuje argumenty i zwraca wartość.
* Rozróżnić argumenty pozycyjne i kluczowe w funkcjach Pythona.

Zwróć listę w formacie Markdown (lista wypunktowana).  Nie dodawaj żadnego tekstu poza listą celów.
    """
    return safe_api_call(content_model, prompt)

def generate_section_content(topic: str, section_title: str, duration: int, key_points: list) -> Optional[str]:
    key_points_str = "\n".join([f"* {point}" for point in key_points])
    prompt = f"""
Jesteś doświadczonym nauczycielem programowania, specjalizującym się w tworzeniu angażujących, zrozumiałych i wyczerpujących materiałów edukacyjnych dla osób na poziomie średniozaawansowanym.

Twoim zadaniem jest opracowanie treści sekcji lekcji o nazwie "{section_title}".
Temat lekcji: {topic}
Czas trwania sekcji: {duration} minut
Poziom trudności: {config.settings['difficulty_level']}
Język: {config.settings['target_language']}

Kluczowe punkty do omówienia (użyj ich jako inspiracji, ale rozwiń je i dodaj własne):
{key_points_str}

Treść powinna być:
* **Szczegółowa i wyczerpująca:**  Nie zakładaj, że uczeń ma dużą wiedzę wstępną.  Wyjaśniaj pojęcia dokładnie, krok po kroku.
* **Dobrze zorganizowana:** Używaj nagłówków, akapitów, list wypunktowanych i numerowanych, aby struktura była przejrzysta.
* **Zawierać definicje:**  Definiuj wszystkie kluczowe pojęcia i terminy.
* **Zawierać praktyczne przykłady:**  Do każdego omawianego pojęcia dodaj *przynajmniej jeden* praktyczny przykład kodu w Pythonie.  Przykłady powinny być proste, ale ilustrujące omawiane zagadnienie.  Używaj *różnych* przykładów (nie tylko jednego, powtarzanego).
* **Zawierać przykłady z życia codziennego (analogie):**  Tam, gdzie to możliwe, używaj analogii z życia codziennego, aby pomóc uczniom zrozumieć abstrakcyjne koncepcje programistyczne.
* **Zawierać fragmenty kodu (sformatowane w blokach kodu Markdown):**  Kod powinien być poprawny składniowo i gotowy do uruchomienia.  Dodawaj komentarze do kodu, aby wyjaśnić, co się dzieje.
* **Zawierać "ciekawostki" (opcjonalnie):**  Jeśli to możliwe, dodaj krótkie, interesujące fakty lub informacje związane z tematem.
* **Zawierać listę typowych błędów (pułapek):**  Po omówieniu każdego kluczowego pojęcia, dodaj sekcję "Typowe Pułapki", w której opiszesz najczęstsze błędy popełniane przez początkujących programistów w związku z tym pojęciem.  Podaj *przykłady* błędnego kodu i wyjaśnij, jak ich unikać.
* **Zawierać listę najlepszych praktyk:** Po omówieniu każdego kluczowego pojęcia, dodaj sekcję "Najlepsze Praktyki", w której opiszesz zalecane sposoby postępowania.
* **Być napisana w języku {config.settings['target_language']}, przystępnym dla poziomu {config.settings['difficulty_level']}.**  Używaj prostego, ale precyzyjnego języka.  Unikaj żargonu, chyba że go zdefiniujesz.
* **Unikać powtórzeń i ogólników.**  Każde zdanie powinno wnosić coś nowego.
* **Być napisana w sposób angażujący.**  Używaj aktywnego głosu, zadawaj pytania, odwołuj się do doświadczeń uczniów.

Używaj formatowania Markdown.  Dbaj o estetykę i czytelność.
    """
    return safe_api_call(content_model, prompt)

def generate_common_pitfalls(topic: str, section_title: str) -> Optional[str]:
    prompt = f"""
Jesteś doświadczonym nauczycielem programowania.  Wiesz, jakie błędy najczęściej popełniają początkujący programiści.

Wygeneruj listę typowych błędów i pułapek (common pitfalls) związanych z tematem "{section_title}" w lekcji o "{topic}".
Poziom trudności: {config.settings['difficulty_level']}
Język: {config.settings['target_language']}

Pułapki powinny być:
* **Konkretne i precyzyjne:**  Opisz *konkretne* błędy, a nie ogólne stwierdzenia.
* **Zawierać przykłady błędnego kodu:**  Do *każdego* błędu dodaj krótki przykład kodu w Pythonie, który ilustruje ten błąd.
* **Zawierać wyjaśnienie, dlaczego dany kod jest błędny:**  Wyjaśnij, *dlaczego* dany błąd jest problemem i jakie są jego konsekwencje.
* **Zawierać wskazówki, jak uniknąć błędu:**  Podaj *konkretne* wskazówki, jak uniknąć danego błędu lub jak go naprawić.
* **Sformułowane w języku {config.settings['target_language']}.**

Zwróć listę w formacie Markdown (lista wypunktowana).  Każdy punkt powinien zawierać:
* Krótki opis błędu.
* Przykład błędnego kodu (w bloku kodu Markdown).
* Wyjaśnienie.
* Wskazówki, jak uniknąć błędu.
    """
    return safe_api_call(content_model, prompt)

def generate_best_practices(topic: str, section_title: str) -> Optional[str]:
    prompt = f"""
Jesteś doświadczonym programistą i nauczycielem programowania.  Znasz najlepsze praktyki kodowania w Pythonie.

Wygeneruj listę najlepszych praktyk (best practices) związanych z tematem "{section_title}" w lekcji o "{topic}".
Poziom trudności: {config.settings['difficulty_level']}
Język: {config.settings['target_language']}

Najlepsze praktyki powinny być:
* **Konkretne i praktyczne:**  Podaj *konkretne* wskazówki, które uczeń może od razu zastosować w swoim kodzie.
* **Uzasadnione:**  Wyjaśnij, *dlaczego* dana praktyka jest uważana za dobrą.  Jakie korzyści przynosi?
* **Zilustrowane przykładami (opcjonalnie):**  Jeśli to możliwe, dodaj krótkie przykłady kodu, które ilustrują daną praktykę.
* **Sformułowane w języku {config.settings['target_language']}.**

Zwróć listę w formacie Markdown (lista wypunktowana).
    """
    return safe_api_call(content_model, prompt)

def generate_assessments(topic: str) -> Optional[Dict[str, Any]]:
    prompt = f"""
Jesteś doświadczonym nauczycielem.
Wygeneruj propozycje oceniania (assessments) dla lekcji o temacie "{topic}".
Poziom trudności: {config.settings['difficulty_level']}
Język: {config.settings['target_language']}

Ocenianie powinno zawierać:
* Ocenianie formatywne (formative assessment): Przykłady, jak sprawdzić zrozumienie w trakcie lekcji.
* Ocenianie sumatywne (summative assessment): Przykłady, jak ocenić opanowanie materiału po lekcji.

Zwróć dane w formacie JSON:
{{
    "formative": ["przykładowe zadanie 1", "przykładowe zadanie 2"],
    "summative": "przykładowe zadanie podsumowujące"
}}
    """
    raw_text = safe_api_call(content_model, prompt)
    if not raw_text:
        return None

    try:
        cleaned_text = clean_json_response(raw_text)
        return json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        logging.error(f"JSON parsing failed (assessments). Raw response:\n{raw_text}")
        return None

def generate_lesson_structure(topic: str) -> Optional[Dict[str, Any]]:
    prompt = f"""
[IMPORTANT] Respond ONLY with valid JSON.  Do not include any text outside of the JSON structure.

Jesteś doświadczonym projektantem kursów edukacyjnych.
Stwórz strukturę lekcji na temat: "{topic}".
Język: {config.settings['target_language']}
Poziom trudności: {config.settings['difficulty_level']}
Całkowity czas trwania lekcji: {config.settings['lesson_length']} minut

Struktura lekcji powinna być w formacie JSON:
{{
    "metadata": {{
        "topic": "{topic}",
        "created": "{datetime.now().isoformat()}",
        "version": "1.0"
    }},
    "sections": [
        {{
            "title": "Tytuł sekcji 1",
            "duration": 15,
            "type": "introduction",
            "key_points": ["Kluczowy punkt 1", "Kluczowy punkt 2"]
        }},
        {{
            "title": "Tytuł sekcji 2",
            "duration": 25,
            "type": "theory",
            "key_points": ["Kluczowy punkt 3", "Kluczowy punkt 4"]
        }}
    ],
    "assessments": {{
        "formative": ["Przykładowe pytanie 1", "Przykładowe pytanie 2"],
        "summative": "Przykładowy quiz"
    }}
}}

Pamiętaj o następujących zasadach:
* Czas trwania wszystkich sekcji musi sumować się do {config.settings['lesson_length']} minut.
* Używaj zróżnicowanych typów sekcji (np. "introduction", "theory", "practice", "discussion", "summary").
* Podawaj kluczowe punkty ("key_points") dla każdej sekcji.
* Uwzględnij ocenianie formatywne i sumatywne.
* Zwracaj TYLKO poprawny JSON.
    """

    raw_text = safe_api_call(structure_model, prompt)
    if not raw_text:
        return None

    try:
        cleaned_text = clean_json_response(raw_text)
        parsed_json = json.loads(cleaned_text)
        return parsed_json
    except json.JSONDecodeError as e:
        logging.error(f"JSON parsing failed (structure). Raw response:\n{raw_text}")
        logging.error(f"JSONDecodeError: {e}")
        return None

class LessonGenerator:
    def __init__(self):
        self.lesson_data = {}

    def generate_full_lesson(self, topic: str) -> Optional[str]:
        """Generates the full lesson content and converts it to HTML."""
        try:
            self.lesson_data = generate_lesson_structure(topic)
            if not self.lesson_data:
                logging.error(f"Lesson structure generation failed for topic: {topic}")
                return None

            for section in self.lesson_data.get('sections', []):
                section_title = section['title']
                duration = section['duration']
                key_points = section.get('key_points', [])

                learning_objectives = generate_learning_objectives(topic, section_title, duration)
                if learning_objectives:
                    section['learning_objectives'] = learning_objectives

                content = generate_section_content(topic, section_title, duration, key_points)
                if content:
                    section['content'] = content

                pitfalls = generate_common_pitfalls(topic, section_title)
                if pitfalls:
                    section['common_pitfalls'] = pitfalls

                best_practices = generate_best_practices(topic, section_title)
                if best_practices:
                    section['best_practices'] = best_practices

            if 'assessments' in self.lesson_data:
                assessments = generate_assessments(topic)
                if assessments:
                    self.lesson_data['assessments'] = assessments

            markdown_output = self._format_to_markdown()
            html_output = self._convert_md_to_html(markdown_output)
            return html_output

        except Exception as e:
            logging.error(f"Critical failure during lesson generation for topic {topic}: {str(e)}")
            return None

    def _format_to_markdown(self) -> str:
        md_content = f"# {self.lesson_data['metadata']['topic']}\n\n"
        md_content += f"**Created**: {self.lesson_data['metadata']['created']}\n"
        md_content += f"**Level**: {config.settings['difficulty_level'].title()}\n"
        md_content += f"**Duration**: {config.settings['lesson_length']} minutes\n\n"

        for section in self.lesson_data.get('sections', []):
            md_content += f"## {section['title']} ({section['duration']} minutes)\n\n"

            if 'learning_objectives' in section:
                md_content += "### Cele Nauki\n" + section['learning_objectives'] + "\n\n"

            if 'content' in section:
                md_content += section['content'] + "\n\n"

            if 'common_pitfalls' in section:
                md_content += "### Typowe Pułapki\n" + section['common_pitfalls'] + "\n\n"

            if 'best_practices' in section:
                md_content += "### Najlepsze Praktyki\n" + section['best_practices'] + "\n\n"

        if 'assessments' in self.lesson_data:
            md_content += "\n## Assessments\n\n"
            if 'formative' in self.lesson_data['assessments']:
                md_content += "**Formative:**\n"
                for assessment in self.lesson_data['assessments']['formative']:
                    md_content += f"* {assessment}\n"
                md_content += "\n"
            if 'summative' in self.lesson_data['assessments']:
                md_content += f"**Summative:** {self.lesson_data['assessments']['summative']}\n"

        return md_content


    def _convert_md_to_html(self, md_content: str) -> str:
        html_content = markdown.markdown(md_content, extensions=['fenced_code', 'codehilite'])

        html_output = f"""<!DOCTYPE html>
<html lang="{config.settings['target_language']}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.lesson_data['metadata']['topic']}</title>
    <style>
        body {{ font-family: sans-serif; line-height: 1.6; }}
        h1, h2, h3 {{ margin-bottom: 0.5em; }}
        ul {{ margin-top: 0.5em; }}
        pre {{ background-color: #f0f0f0; padding: 1em; overflow-x: auto; }}
        .codehilite .err {{color: red;}}
    </style>
</head>
<body>
    {html_content}
</body>
</html>
"""
        return html_output

def read_topics_from_file(filepath: str) -> list[str]:
    """Reads lesson topics from a file, one topic per line."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            topics = [line.strip() for line in f if line.strip()]  # Read and clean lines
        return topics
    except FileNotFoundError:
        logging.error(f"Error: Topics file not found: {filepath}")
        return []
    except Exception as e:
        logging.error(f"Error reading topics file: {e}")
        return []

# --- Main Execution ---
if __name__ == "__main__":
    generator = LessonGenerator()
    topics_file = config.settings['topics_file']
    output_dir = config.settings['output_dir']

    topics = read_topics_from_file(topics_file)
    if not topics:
        print("No topics found.  Please add topics to 'topics.txt', one topic per line.")
        exit()

    os.makedirs(output_dir, exist_ok=True)  # Ensure output directory exists

    for topic in topics:
        logging.info(f"Starting generation for topic: {topic}")
        html_lesson = generator.generate_full_lesson(topic)

        if html_lesson:
            filename = f"lesson_{topic.replace(' ', '_').replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            filepath = os.path.join(output_dir, filename)
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(html_lesson)
                logging.info(f"Success! Lesson for topic '{topic}' saved to {filepath}")
            except Exception as e:
                logging.error(f"Failed to save lesson for topic '{topic}' to file: {e}")
        else:
            logging.error(f"Generation failed for topic: {topic}")

    print("Lesson generation complete.  Check the logs for details.")