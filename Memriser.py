from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from deep_translator import GoogleTranslator
import time
import re
from dotenv import load_dotenv
import os
import unicodedata
import difflib
import json
ASCII_ART = r"""
███╗   ███╗███████╗███╗   ███╗██████╗ ██╗███████╗███████╗██████╗ 
████╗ ████║██╔════╝████╗ ████║██╔══██╗██║██╔════╝██╔════╝██╔══██╗
██╔████╔██║█████╗  ██╔████╔██║██████╔╝██║███████╗█████╗  ██████╔╝
██║╚██╔╝██║██╔══╝  ██║╚██╔╝██║██╔══██╗██║╚════██║██╔══╝  ██╔══██╗
██║ ╚═╝ ██║███████╗██║ ╚═╝ ██║██║  ██║██║███████║███████╗██║  ██║
╚═╝     ╚═╝╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚═╝  ╚═╝
"""
RED = "\033[91m"
RESET = "\033[0m"
print(RED + ASCII_ART + RESET)
load_dotenv()
EMAIL = os.getenv("MEMRISE_EMAIL")
PASSWORD = os.getenv("MEMRISE_PASSWORD")
SYN_OVERRIDES = {}
OVERRIDE_FILE = "syn_overrides.json"
if os.path.exists(OVERRIDE_FILE):
    with open(OVERRIDE_FILE, "r", encoding="utf-8") as f:
        SYN_OVERRIDES.update(json.load(f))
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)
driver.get("https://community-courses.memrise.com/dashboard")
wait = WebDriverWait(driver, 15)
def normalize(text):
    text = text.lower()
    text = ''.join(c for c in unicodedata.normalize('NFD', text)
                   if unicodedata.category(c) != 'Mn')
    return text
normalized_overrides = {k: [normalize(a) for a in v] for k,v in SYN_OVERRIDES.items()}
translation_cache = {}
def clean_answer(text):
    text = re.sub(r"\([^)]*\)", "", text)
    return text.strip().lower()
def clean_prompt(text):
    return text.split(",")[0].strip().lower()
def clean_translation(text):
    return text.split(";")[0].split(",")[0].strip().lower()
def fuzzy_equal(a, b):
    a = clean_answer(a)
    b = clean_answer(b)
    return (
        a == b or
        a in b or
        b in a or
        a.replace("la ", "").replace("le ", "").replace("l'", "") ==
        b.replace("la ", "").replace("le ", "").replace("l'", "")
    )
def wait_for_element(selector, by=By.CSS_SELECTOR, timeout=5, poll=0.5):
    end_time = time.time() + timeout
    while True:
        try:
            elem = driver.find_element(by, selector)
            return elem
        except:
            try:
                retry_btn = driver.find_element(By.XPATH, "//button[.//div[text()='Retry']]")
                if retry_btn.get_attribute("disabled") or "disabled" in retry_btn.get_attribute("class").lower():
                    print(f"{RED}Retry button disabled, reloading page...{RESET}")
                    driver.get(driver.current_url)
                    time.sleep(1)
                else:
                    retry_btn.click()
                    print(f"{RED}Clicked Retry button because element {selector} was not found{RESET}")
            except:
                pass
            time.sleep(poll)
        if time.time() > end_time:
            end_time = time.time() + timeout
            print(f"Waiting for element: {selector}...")
def wait_for_elements(selector, by=By.CSS_SELECTOR, timeout=5, poll=0.5):
    end_time = time.time() + timeout
    while True:
        try:
            elems = driver.find_elements(by, selector)
            if elems:
                return elems
        except:
            pass
        try:
            retry_btn = driver.find_element(By.XPATH, "//button[.//div[text()='Retry']]")
            if retry_btn.get_attribute("disabled") or "disabled" in retry_btn.get_attribute("class").lower():
                print(f"{RED}Retry button disabled, reloading page...{RESET}")
                driver.get(driver.current_url)
                time.sleep(1)
            else:
                retry_btn.click()
                print(f"{RED}Clicked Retry button because element {selector} was not found{RESET}")
        except:
            pass
        time.sleep(poll)
        if time.time() > end_time:
            end_time = time.time() + timeout
            print(f"Waiting for elements: {selector}...")
def get_phrase():
    elem = wait_for_element('[data-testid="learn-prompt-text"] span')
    return elem.text.strip()
def get_points():
    spans = driver.find_elements(By.CSS_SELECTOR, "span")
    for s in spans:
        text = s.text.strip()
        if text.isdigit():
            return int(text)
    return 0
def get_points():
    spans = driver.find_elements(By.CSS_SELECTOR, "span") 
    for s in spans: 
        text = s.text.strip() 
        if text.isdigit(): 
            return int(text) 
    return 0
def legacy_get_answers(retries=3, wait_time=0.02):
    for attempt in range(retries):
        try:
            spans = wait_for_elements('span[dir="auto"]')
            results = []
            for s in spans:
                try:
                    txt = s.text.strip()
                except:
                    continue
                parent = s
                button = None
                for _ in range(6):
                    try:
                        parent = parent.find_element(By.XPATH, "..")
                        if parent.tag_name.lower() == "button":
                            button = parent
                            break
                    except:
                        continue
                if button:
                    num = None
                    try:
                        num_el = button.find_element(By.CSS_SELECTOR, 'div[class*="label"], span[class*="label"]')
                        num_text = num_el.text.strip()
                        if num_text.isdigit():
                            num = num_text
                    except:
                        pass
                    results.append({
                        "button": button,
                        "text": txt,
                        "number": num
                    })
            return results
        except Exception as e:
            time.sleep(wait_time)
    return []
def get_answers():
    answers = []
    try:
        container = wait_for_element('div.sc-sxv7ci-0.dsHgwW')
        buttons = container.find_elements(By.CSS_SELECTOR, 'button')
        for btn in buttons:
            try:
                num_el = btn.find_element(By.CSS_SELECTOR, 'div.sc-eqYatC, span.sc-eqYatC')
                num = num_el.text.strip() if num_el.text.strip().isdigit() else None
                text_el = btn.find_element(By.CSS_SELECTOR, 'div.sc-lgpSej span[dir="auto"]')
                text = text_el.text.strip()
                answers.append({
                    "button": btn,
                    "text": text,
                    "number": num
                })
            except:
                continue
    except:
        pass
    return answers
print("Logging in...")
email_box = wait_for_element('input#username[data-testid="signinUsernameInput"]')
email_box.clear()
email_box.send_keys(EMAIL)
pass_box = wait_for_element('input#password[data-testid="signinPasswordInput"]')
pass_box.clear()
pass_box.send_keys(PASSWORD)
login_btn = wait_for_element('button[data-testid="signinFormSubmit"]')
login_btn.click()
print("Logged in, opening speed review...")
btn1 = wait_for_element('[data-testid="ms-button-6474964"]')
btn1.click()
btn2 = wait_for_element('[data-testid="ms-unlocked-speed_review"]')
btn2.click()
RED = "\033[92m"
RESET = "\033[0m"
time.sleep(2)
wrong_count = 0
while True:
    raw_prompt = get_phrase()
    prompt = clean_prompt(raw_prompt)
    old_points = get_points()
    if prompt in normalized_overrides:
        valid_answers = normalized_overrides[prompt]
    elif prompt in translation_cache:
        valid_answers = [translation_cache[prompt]]
    else:
        fr = GoogleTranslator(source="en", target="fr").translate(prompt)
        trans_clean = normalize(clean_translation(fr))
        translation_cache[prompt] = trans_clean
        valid_answers = [trans_clean]
    answers = get_answers()
    match = None
    best_ratio = 0
    for a in answers:
        ans_norm = normalize(clean_answer(a["text"]))
        for opt_norm in valid_answers:
            if ans_norm == opt_norm:
                match = a
                best_ratio = 1
                break
            ratio = difflib.SequenceMatcher(None, ans_norm, opt_norm).ratio()
            if ratio > best_ratio:
                match = a
                best_ratio = ratio
        if best_ratio >= 0.9:
            break
    if match is None:
        match = answers[0]
    try:
        match["button"].click()
    except:
        answers = get_answers()
        for a in answers:
            if a["text"] == match["text"]:
                match["button"] = a["button"]
                a["button"].click()
                break
    correct_answer = None
    for a in answers:
        try:
            bg_color = driver.execute_script(
                "return window.getComputedStyle(arguments[0]).backgroundColor;", a["button"]
            )
        except:
            continue
        if bg_color.replace(" ", "") == "rgb(141,238,210)":
            correct_answer = clean_answer(a["text"])
            if prompt not in SYN_OVERRIDES:
                SYN_OVERRIDES[prompt] = [correct_answer]
            elif correct_answer not in SYN_OVERRIDES[prompt]:
                SYN_OVERRIDES[prompt].append(correct_answer)
            normalized_overrides[prompt] = [normalize(ans) for ans in SYN_OVERRIDES[prompt]]
            with open(OVERRIDE_FILE, "w", encoding="utf-8") as f:
                json.dump(SYN_OVERRIDES, f, ensure_ascii=False, indent=4)
            break
    driver.switch_to.active_element.send_keys(Keys.ENTER)
    new_points = get_points()
    if new_points <= old_points:
        print(f"\u001b[31mGOT WRONG: {prompt} -> gave: {match['text']} | correct: {correct_answer}{RESET}")