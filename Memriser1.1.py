import os
import json
import time
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import unicodedata
import difflib
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    StaleElementReferenceException
)
from deep_translator import GoogleTranslator
from dotenv import load_dotenv
ASCII_ART = r"""
███╗   ███╗███████╗███╗   ███╗██████╗ ██╗███████╗███████╗██████╗ 
████╗ ████║██╔════╝████╗ ████║██╔══██╗██║██╔════╝██╔════╝██╔══██╗
██╔████╔██║█████╗  ██╔████╔██║██████╔╝██║███████╗█████╗  ██████╔╝
██║╚██╔╝██║██╔══╝  ██║╚██╔╝██║██╔══██╗██║╚════██║██╔══╝  ██╔══██╗
██║ ╚═╝ ██║███████╗██║ ╚═╝ ██║██║  ██║██║███████║███████╗██║  ██║
╚═╝     ╚═╝╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚═╝  ╚═╝
"""
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_RESET = "\033[0m"
OVERRIDE_FILE = "syn_overrides.json"
STATS_FILE = "bot_stats.json"
CONFIG_FILE = "bot_config.json"
MEMRISE_DASHBOARD_URL = "https://community-courses.memrise.com/dashboard"
SELECTOR_LOGIN_EMAIL = 'input#username[data-testid="signinUsernameInput"]'
SELECTOR_LOGIN_PASSWORD = 'input#password[data-testid="signinPasswordInput"]'
SELECTOR_LOGIN_BUTTON = 'button[data-testid="signinFormSubmit"]'
SELECTOR_COURSE_BUTTON = '[data-testid="ms-button-6474964"]'
SELECTOR_SPEED_REVIEW_BUTTON = '[data-testid="ms-unlocked-speed_review"]'
SELECTOR_PROMPT_TEXT = '[data-testid="learn-prompt-text"] span'
SELECTOR_RETRY_BUTTON = "//button[.//div[text()='Retry']]"
SELECTOR_ANSWER_CONTAINER = 'div.sc-sxv7ci-0.dsHgwW'
SELECTOR_ANSWER_BUTTONS = 'button'
SELECTOR_ANSWER_NUMBER = 'div.sc-eqYatC, span.sc-eqYatC'
SELECTOR_ANSWER_TEXT = 'div.sc-lgpSej span[dir="auto"]'
DEFAULT_CONFIG = {
    "wait_timeout": 15,
    "similarity_threshold": 0.9,
    "source_language": "en",
    "target_language": "fr",
    "dry_run": False
}
CORRECT_ANSWER_BG_COLOR = "rgb(141,238,210)"
@dataclass
class Answer:
    button: Any
    text: str
    number: Optional[str] = None
@dataclass
class Statistics:
    total_questions: int = 0
    correct_answers: int = 0
    wrong_answers: int = 0
    @property
    def accuracy(self) -> float:
        if self.total_questions == 0:
            return 0.0
        return (self.correct_answers / self.total_questions) * 100
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_questions": self.total_questions,
            "correct_answers": self.correct_answers,
            "wrong_answers": self.wrong_answers,
            "accuracy": self.accuracy
        }
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Statistics':
        return cls(
            total_questions=data.get("total_questions", 0),
            correct_answers=data.get("correct_answers", 0),
            wrong_answers=data.get("wrong_answers", 0)
        )
def setup_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('memrise_bot.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)
def normalize_text(text: str) -> str:
    text = text.lower()
    text = ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )
    return text
def clean_answer(text: str) -> str:
    import re
    text = re.sub(r"\([^)]*\)", "", text)
    return text.strip().lower()
def clean_prompt(text: str) -> str:
    return text.split(",")[0].strip().lower()
def clean_translation(text: str) -> str:
    return text.split(";")[0].split(",")[0].strip().lower()
def load_json_file(filepath: str, default: Any = None) -> Any:
    if not os.path.exists(filepath):
        return default if default is not None else {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logging.error(f"Error loading {filepath}: {e}")
        return default if default is not None else {}
def save_json_file(filepath: str, data: Any) -> None:
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except IOError as e:
        logging.error(f"Error saving {filepath}: {e}")
class TranslationCache:
    def __init__(self, source_lang: str, target_lang: str):
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.cache: Dict[str, str] = {}
        self.translator = GoogleTranslator(source=source_lang, target=target_lang)
    def get_translation(self, text: str) -> str:
        if text in self.cache:
            return self.cache[text]
        try:
            translation = self.translator.translate(text)
            cleaned = normalize_text(clean_translation(translation))
            self.cache[text] = cleaned
            return cleaned
        except Exception as e:
            logging.error(f"Translation error for '{text}': {e}")
            raise
class AnswerOverrideManager:
    def __init__(self, filepath: str = OVERRIDE_FILE):
        self.filepath = filepath
        self.overrides: Dict[str, List[str]] = load_json_file(filepath, {})
        self.normalized_overrides = self._normalize_overrides()
    def _normalize_overrides(self) -> Dict[str, List[str]]:
        return {
            k: [normalize_text(a) for a in v]
            for k, v in self.overrides.items()
        }
    def get_valid_answers(self, prompt: str) -> Optional[List[str]]:
        return self.normalized_overrides.get(prompt)
    def add_correct_answer(self, prompt: str, answer: str) -> None:
        if prompt not in self.overrides:
            self.overrides[prompt] = [answer]
        elif answer not in self.overrides[prompt]:
            self.overrides[prompt].append(answer)
        self.normalized_overrides[prompt] = [
            normalize_text(ans) for ans in self.overrides[prompt]
        ]
        self.save()
    def save(self) -> None:
        save_json_file(self.filepath, self.overrides)
class AnswerMatcher:
    def __init__(self, similarity_threshold: float = 0.9):
        self.similarity_threshold = similarity_threshold
    def find_best_match(
        self,
        answers: List[Answer],
        valid_answers: List[str]
    ) -> Answer:
        best_match = None
        best_ratio = 0
        for answer in answers:
            ans_norm = normalize_text(clean_answer(answer.text))
            for valid_ans in valid_answers:
                if ans_norm == valid_ans:
                    return answer
                ratio = difflib.SequenceMatcher(None, ans_norm, valid_ans).ratio()
                if ratio > best_ratio:
                    best_match = answer
                    best_ratio = ratio
            if best_ratio >= self.similarity_threshold:
                break
        return best_match if best_match else answers[0]
class MemriseBot:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.logger = setup_logging()
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        load_dotenv()
        self.email = os.getenv("MEMRISE_EMAIL")
        self.password = os.getenv("MEMRISE_PASSWORD")
        if not self.email or not self.password:
            raise ValueError(
                "MEMRISE_EMAIL and MEMRISE_PASSWORD must be set in .env file"
            )
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.translation_cache = TranslationCache(
            self.config["source_language"],
            self.config["target_language"]
        )
        self.override_manager = AnswerOverrideManager()
        self.answer_matcher = AnswerMatcher(self.config["similarity_threshold"])
        self.stats = Statistics.from_dict(load_json_file(STATS_FILE, {}))
        self.logger.info("MemriseBot initialized")
    def setup_driver(self) -> None:
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, self.config["wait_timeout"])
        self.logger.info("Chrome driver initialized")
    def cleanup(self) -> None:
        if self.driver:
            self.logger.info("Closing browser...")
            self.driver.quit()
        save_json_file(STATS_FILE, self.stats.to_dict())
        self.logger.info(f"Statistics saved - Accuracy: {self.stats.accuracy:.2f}%")
    def wait_for_element(
        self,
        selector: str,
        by: By = By.CSS_SELECTOR,
        timeout: Optional[int] = None
    ) -> Any:
        timeout = timeout or self.config["wait_timeout"]
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                element = self.driver.find_element(by, selector)
                return element
            except NoSuchElementException:
                self._check_retry_button()
                time.sleep(0.5)
        raise TimeoutException(f"Element {selector} not found after {timeout}s")
    def wait_for_elements(
        self,
        selector: str,
        by: By = By.CSS_SELECTOR,
        timeout: Optional[int] = None
    ) -> List[Any]:
        timeout = timeout or self.config["wait_timeout"]
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                elements = self.driver.find_elements(by, selector)
                if elements:
                    return elements
            except Exception as e:
                self.logger.debug(f"Error finding elements: {e}")
            self._check_retry_button()
            time.sleep(0.5)
        raise TimeoutException(f"Elements {selector} not found after {timeout}s")
    def _check_retry_button(self) -> None:
        try:
            retry_btn = self.driver.find_element(By.XPATH, SELECTOR_RETRY_BUTTON)
            is_disabled = (
                retry_btn.get_attribute("disabled") or
                "disabled" in retry_btn.get_attribute("class").lower()
            )
            if is_disabled:
                self.logger.info("Reloading...")
                self.driver.get(self.driver.current_url)
                time.sleep(1)
            else:
                retry_btn.click()
                self.logger.info("Clicked Retry button")
        except NoSuchElementException:
            pass
    def login(self) -> None:
        self.logger.info("Logging in...")
        self.driver.get(MEMRISE_DASHBOARD_URL)
        email_box = self.wait_for_element(SELECTOR_LOGIN_EMAIL)
        email_box.clear()
        email_box.send_keys(self.email)
        pass_box = self.wait_for_element(SELECTOR_LOGIN_PASSWORD)
        pass_box.clear()
        pass_box.send_keys(self.password)
        login_btn = self.wait_for_element(SELECTOR_LOGIN_BUTTON)
        login_btn.click()
        self.logger.info("Logged in successfully")
    def start_speed_review(self) -> None:
        self.logger.info("Starting speed review...")
        course_btn = self.wait_for_element(SELECTOR_COURSE_BUTTON)
        course_btn.click()
        review_btn = self.wait_for_element(SELECTOR_SPEED_REVIEW_BUTTON)
        review_btn.click()
        time.sleep(2)
        self.logger.info("Speed review started")
    def get_prompt(self) -> str:
        elem = self.wait_for_element(SELECTOR_PROMPT_TEXT)
        return elem.text.strip()
    def get_points(self) -> int:
        try:
            spans = self.driver.find_elements(By.CSS_SELECTOR, "span")
            for span in spans:
                text = span.text.strip()
                if text.isdigit():
                    return int(text)
        except Exception as e:
            self.logger.debug(f"Error getting points: {e}")
        return 0
    def get_answers(self) -> List[Answer]:
        answers = []
        try:
            container = self.wait_for_element(SELECTOR_ANSWER_CONTAINER)
            buttons = container.find_elements(By.CSS_SELECTOR, SELECTOR_ANSWER_BUTTONS)
            for btn in buttons:
                try:
                    num_el = btn.find_element(By.CSS_SELECTOR, SELECTOR_ANSWER_NUMBER)
                    num = num_el.text.strip() if num_el.text.strip().isdigit() else None
                    text_el = btn.find_element(By.CSS_SELECTOR, SELECTOR_ANSWER_TEXT)
                    text = text_el.text.strip()
                    answers.append(Answer(button=btn, text=text, number=num))
                except NoSuchElementException:
                    continue
        except TimeoutException:
            self.logger.error("Could not find answer container")
        return answers
    def click_answer(self, answer: Answer) -> None:
        try:
            answer.button.click()
        except StaleElementReferenceException:
            self.logger.warning("Stale element, refreshing answers...")
            answers = self.get_answers()
            for ans in answers:
                if ans.text == answer.text:
                    ans.button.click()
                    break
    def find_correct_answer(self, answers: List[Answer]) -> Optional[str]:
        for answer in answers:
            try:
                bg_color = self.driver.execute_script(
                    "return window.getComputedStyle(arguments[0]).backgroundColor;",
                    answer.button
                )
                if bg_color.replace(" ", "") == CORRECT_ANSWER_BG_COLOR:
                    return clean_answer(answer.text)
            except Exception as e:
                self.logger.debug(f"Error checking answer color: {e}")
                continue
        return None
    def process_question(self) -> None:
        raw_prompt = self.get_prompt()
        prompt = clean_prompt(raw_prompt)
        old_points = self.get_points()
        valid_answers = self.override_manager.get_valid_answers(prompt)
        if valid_answers is None:
            translation = self.translation_cache.get_translation(prompt)
            valid_answers = [translation]
        answers = self.get_answers()
        if not answers:
            self.logger.error("No answers found!")
            return
        selected_answer = self.answer_matcher.find_best_match(answers, valid_answers)
        if self.config["dry_run"]:
            self.logger.info(
                f"DRY RUN - Would select: {selected_answer.text} for prompt: {prompt}"
            )
            return
        self.click_answer(selected_answer)
        correct_answer = self.find_correct_answer(answers)
        if correct_answer:
            self.override_manager.add_correct_answer(prompt, correct_answer)
        self.driver.switch_to.active_element.send_keys(Keys.ENTER)
        new_points = self.get_points()
        self.stats.total_questions += 1
        if new_points > old_points:
            self.stats.correct_answers += 1
            self.logger.info(
                f"{COLOR_GREEN}CORRECT: {prompt} -> {selected_answer.text}{COLOR_RESET}"
            )
        else:
            self.stats.wrong_answers += 1
            self.logger.error(
                f"{COLOR_RED}WRONG: {prompt} -> gave: {selected_answer.text} | "
                f"correct: {correct_answer}{COLOR_RESET}"
            )
    def run(self) -> None:
        print(COLOR_RED + ASCII_ART + COLOR_RESET)
        try:
            self.setup_driver()
            self.login()
            self.start_speed_review()
            self.logger.info("Starting main loop...")
            while True:
                try:
                    self.process_question()
                except KeyboardInterrupt:
                    self.logger.info("Interrupted by user")
                    break
                except Exception as e:
                    self.logger.error(f"Error processing question: {e}", exc_info=True)
                    time.sleep(1)
        finally:
            self.cleanup()
def main():
    config = load_json_file(CONFIG_FILE, DEFAULT_CONFIG)
    bot = MemriseBot(config)
    bot.run()
if __name__ == "__main__":
    main()