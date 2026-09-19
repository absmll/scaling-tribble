import json
import os
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
import streamlit as st
from bs4 import BeautifulSoup
from fpdf import FPDF

st.set_page_config(page_title="أداة فحص المتاجر الإلكترونية", page_icon="🔍", layout="wide")

LUXURY_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Cairo', sans-serif;
    direction: rtl;
}

.stApp {
    background: radial-gradient(circle at top right, #1a1f2e 0%, #0d1117 55%, #0a0c10 100%);
}

.hero {
    background: linear-gradient(135deg, #1c2333 0%, #10131c 100%);
    border: 1px solid rgba(212, 175, 55, 0.25);
    border-radius: 18px;
    padding: 2.2rem 2rem;
    margin-bottom: 1.8rem;
    text-align: center;
    box-shadow: 0 10px 30px rgba(0,0,0,0.35);
}
.hero h1 {
    font-weight: 800;
    font-size: 2.1rem;
    background: linear-gradient(90deg, #d4af37, #f5e7a8, #d4af37);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.4rem;
}
.hero p { color: #9aa4b2; font-size: 1rem; margin: 0; }

.metric-row { display: flex; gap: 1rem; margin: 1.2rem 0; }
.metric-card {
    flex: 1;
    background: linear-gradient(160deg, #171c28, #11141c);
    border: 1px solid rgba(212,175,55,0.18);
    border-radius: 14px;
    padding: 1.1rem 1rem;
    text-align: center;
    box-shadow: 0 6px 18px rgba(0,0,0,0.25);
}
.metric-card .label { color: #9aa4b2; font-size: 0.85rem; margin-bottom: 0.3rem; }
.metric-card .value { color: #f5e7a8; font-size: 1.9rem; font-weight: 800; }

.section-card {
    background: rgba(23, 28, 40, 0.65);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px;
    padding: 1.3rem 1.4rem;
    margin-bottom: 1rem;
}
.section-card h3 {
    color: #d4af37;
    font-weight: 700;
    margin-top: 0;
    border-bottom: 1px solid rgba(212,175,55,0.2);
    padding-bottom: 0.5rem;
    margin-bottom: 0.8rem;
}

.stButton > button, .stDownloadButton > button, .stLinkButton > a {
    border-radius: 10px !important;
    font-weight: 700 !important;
    border: 1px solid rgba(212,175,55,0.4) !important;
}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
    background: linear-gradient(135deg, #d4af37, #b8912c) !important;
    color: #10131c !important;
}

.pill { display:inline-block; padding: 0.15rem 0.65rem; border-radius: 999px; font-size: 0.8rem; font-weight:700; margin-inline-end: 0.4rem; margin-bottom: 0.35rem;}
.pill-ok { background: rgba(46, 204, 113, 0.15); color: #2ecc71; border: 1px solid rgba(46,204,113,0.35); }
.pill-bad { background: rgba(231, 76, 60, 0.15); color: #e74c3c; border: 1px solid rgba(231,76,60,0.35); }

/* Circular score gauges */
.gauge-row { display: flex; gap: 1.5rem; justify-content: center; margin: 1.6rem 0 2rem; flex-wrap: wrap; }
.gauge-wrap { text-align: center; }
.gauge {
    width: 112px; height: 112px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    margin: 0 auto 0.6rem;
    box-shadow: 0 8px 22px rgba(0,0,0,0.35);
}
.gauge-inner {
    width: 88px; height: 88px; border-radius: 50%;
    background: #11141c;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.45rem; font-weight: 800; color: #f5e7a8;
    border: 1px solid rgba(255,255,255,0.05);
}
.gauge-label { color: #9aa4b2; font-size: 0.88rem; font-weight: 600; }

/* Section divider label */
.section-eyebrow {
    color: #d4af37; font-size: 0.75rem; font-weight: 800; letter-spacing: 0.08em;
    text-transform: uppercase; margin: 1.6rem 0 0.5rem;
}

div[data-testid="stExpander"] {
    background: rgba(23, 28, 40, 0.5);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px;
    margin-bottom: 0.6rem;
}

hr { border-color: rgba(255,255,255,0.08) !important; }

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #12151f 0%, #0a0c10 100%);
    border-inline-end: 1px solid rgba(212,175,55,0.15);
}
</style>
"""
st.markdown(LUXURY_CSS, unsafe_allow_html=True)


def hero(title, subtitle):
    st.markdown(f"""
    <div class="hero">
        <h1>{title}</h1>
        <p>{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


def metric_row(items):
    cards = "".join(
        f'<div class="metric-card"><div class="label">{label}</div>'
        f'<div class="value">{value}</div></div>'
        for label, value in items
    )
    st.markdown(f'<div class="metric-row">{cards}</div>', unsafe_allow_html=True)


def _gauge_color(score):
    if score is None:
        return "#4a5063"
    if score >= 75:
        return "#2ecc71"
    if score >= 45:
        return "#d4af37"
    return "#e74c3c"


def gauge_row(items):
    """items: قائمة من (label, score 0-100 أو None)."""
    cells = []
    for label, score in items:
        display_score = score if score is not None else 0
        color = _gauge_color(score)
        value_text = f"{score}" if score is not None else "—"
        cells.append(f"""
        <div class="gauge-wrap">
            <div class="gauge" style="background: conic-gradient({color} {display_score}%, rgba(255,255,255,0.07) 0);">
                <div class="gauge-inner">{value_text}</div>
            </div>
            <div class="gauge-label">{label}</div>
        </div>
        """)
    st.markdown(f'<div class="gauge-row">{"".join(cells)}</div>', unsafe_allow_html=True)


def section_eyebrow(text):
    st.markdown(f'<div class="section-eyebrow">{text}</div>', unsafe_allow_html=True)


def pill(ok, text):
    cls = "pill-ok" if ok else "pill-bad"
    icon = "✔" if ok else "✘"
    return f'<span class="pill {cls}">{icon} {text}</span>'


FONT_PATH = os.path.join(os.path.dirname(__file__), "NotoNaskhArabic-Regular.ttf")


def ar(text):
    """يعيد النص كما هو دون تشكيل خاص، تمهيدًا لطباعته داخل ملف PDF."""
    if text is None:
        return ""
    return str(text)


class ReportPDF(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font("Arabic", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, ar(f"صفحة {self.page_no()}"), align="C")


def new_pdf():
    pdf = ReportPDF()
    pdf.add_font("Arabic", "", FONT_PATH)
    pdf.set_font("Arabic", "", 12)
    pdf.add_page()
    return pdf


def pdf_title(pdf, text, size=18):
    pdf.set_font("Arabic", "", size)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 12, ar(text), align="R", new_x="LMARGIN", new_y="NEXT")


def pdf_subtitle(pdf, text):
    pdf.ln(2)
    pdf.set_font("Arabic", "", 14)
    pdf.set_text_color(30, 90, 160)
    pdf.cell(0, 10, ar(text), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(20, 20, 20)


def pdf_line(pdf, label, ok=None, value=None):
    pdf.set_font("Arabic", "", 11)
    prefix = ""
    if ok is True:
        prefix = "✔ "
        pdf.set_text_color(30, 140, 60)
    elif ok is False:
        prefix = "✘ "
        pdf.set_text_color(190, 40, 40)
    else:
        pdf.set_text_color(20, 20, 20)
    text = f"{prefix}{label}" + (f": {value}" if value not in (None, "") else "")
    pdf.multi_cell(0, 8, ar(text), align="R")
    pdf.set_text_color(20, 20, 20)


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

PRICE_PATTERN = re.compile(
    r"(?:ر\.?س|SAR|EGP|USD|\$|ريال)\s?[\d,]+(?:\.\d+)?|[\d,]+(?:\.\d+)?\s?(?:ر\.?س|SAR|EGP|USD|\$|ريال)",
    re.IGNORECASE,
)

PRODUCT_SELECTOR = "[class*=product], [class*=Product], [id*=product], [class*=item-card]"
PRICE_CLASS_SELECTOR = "[class*=price], [class*=Price], [class*=amount], [class*=Amount]"
TITLE_CLASS_SELECTOR = "[class*=title], [class*=Title], [class*=name], [class*=Name]"


def fetch_html(url, timeout=15):
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text, resp.elapsed.total_seconds(), len(resp.content)


def check_seo(soup, base_url):
    result = {}
    title = soup.find("title")
    result["title"] = title.text.strip() if title else None
    result["title_length"] = len(result["title"]) if result["title"] else 0
    result["title_ok"] = 10 <= result["title_length"] <= 65

    meta_desc = soup.find("meta", attrs={"name": "description"})
    result["meta_description"] = meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else None
    result["meta_description_ok"] = bool(result["meta_description"]) and 50 <= len(result["meta_description"] or "") <= 160

    h1_tags = soup.find_all("h1")
    result["h1_count"] = len(h1_tags)
    result["h1_ok"] = len(h1_tags) == 1

    og_tags = soup.find_all("meta", attrs={"property": re.compile(r"^og:")})
    result["has_open_graph"] = len(og_tags) > 0

    json_ld = soup.find_all("script", attrs={"type": "application/ld+json"})
    result["has_structured_data"] = len(json_ld) > 0

    imgs = soup.find_all("img")
    imgs_no_alt = [i for i in imgs if not i.get("alt", "").strip()]
    result["total_images"] = len(imgs)
    result["images_missing_alt"] = len(imgs_no_alt)

    viewport = soup.find("meta", attrs={"name": "viewport"})
    result["has_mobile_viewport"] = bool(viewport)

    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    for path, key in [("/sitemap.xml", "sitemap_found"), ("/robots.txt", "robots_txt_found")]:
        try:
            r = requests.get(root + path, headers=HEADERS, timeout=8)
            result[key] = r.status_code == 200
        except requests.RequestException:
            result[key] = False
    return result


def check_ux(soup, html, url):
    result = {}
    result["has_search_box"] = bool(soup.find("input", attrs={"type": "search"}) or
                                     soup.find(attrs={"placeholder": re.compile("search|بحث", re.I)}))
    result["has_cart_icon"] = bool(re.search(r"cart|سلة|basket", html, re.I))
    result["has_whatsapp_or_chat"] = bool(re.search(r"whatsapp|wa\.me|livechat|zendesk|crisp|tawk", html, re.I))
    result["uses_https"] = url.startswith("https://")
    return result


TRACKING_TOOLS = [
    ("google_ads", "إعلانات جوجل (Google Ads)", r"googleadservices\.com|google_conversion_id|gtag\(\s*['\"]config['\"]\s*,\s*['\"]AW-"),
    ("google_analytics", "تحليلات جوجل (GA4 / Universal Analytics)", r"gtag\(\s*['\"]config['\"]\s*,\s*['\"]G-|googletagmanager\.com/gtag/js|UA-\d{4,}-\d+"),
    ("google_tag_manager", "مدير الوسوم (Google Tag Manager)", r"googletagmanager\.com/gtm\.js|GTM-[A-Z0-9]+"),
    ("meta_pixel", "بيكسل ميتا/فيسبوك (Meta Pixel)", r"connect\.facebook\.net.*fbevents\.js|fbq\(\s*['\"]init['\"]"),
    ("tiktok_pixel", "بيكسل تيك توك (TikTok Pixel)", r"analytics\.tiktok\.com|ttq\.load"),
    ("snapchat_pixel", "بيكسل سناب شات (Snapchat Pixel)", r"sc-static\.net.*pixel|snaptr\("),
]

CONVERSION_EVENTS = [
    ("purchase", "حدث إتمام الشراء (Purchase)", r"fbq\(\s*['\"]track['\"]\s*,\s*['\"]Purchase|gtag\(\s*['\"]event['\"]\s*,\s*['\"]purchase|ttq\.track\(\s*['\"]CompletePayment|'CompletePayment'"),
    ("add_to_cart", "حدث الإضافة للسلة (AddToCart)", r"fbq\(\s*['\"]track['\"]\s*,\s*['\"]AddToCart|gtag\(\s*['\"]event['\"]\s*,\s*['\"]add_to_cart|ttq\.track\(\s*['\"]AddToCart"),
]


def check_tracking_tools(html):
    """
    يفحص وجود أكواد أدوات تتبع الإعلانات والتحويلات الأكثر شيوعًا. هذا فحص
    يعتمد على وجود الكود في الصفحة فقط (لا يؤكد أن التتبع يعمل فعليًا أو أن
    الحدث يُطلَق بنجاح)، وهدفه لفت الانتباه إلى غياب التتبع كليًا، وهي حالة
    شائعة تؤدي إلى إهدار الميزانية الإعلانية دون علم صاحب المتجر.
    """
    tools_found = {}
    for key, label, pattern in TRACKING_TOOLS:
        tools_found[key] = {"label": label, "found": bool(re.search(pattern, html, re.IGNORECASE))}

    events_found = {}
    for key, label, pattern in CONVERSION_EVENTS:
        events_found[key] = {"label": label, "found": bool(re.search(pattern, html, re.IGNORECASE))}

    any_ad_tool = tools_found["google_ads"]["found"] or tools_found["meta_pixel"]["found"] or \
        tools_found["tiktok_pixel"]["found"] or tools_found["snapchat_pixel"]["found"]
    any_analytics = tools_found["google_analytics"]["found"] or tools_found["google_tag_manager"]["found"]

    return {
        "tools": tools_found,
        "events": events_found,
        "has_any_ad_tracking": any_ad_tool,
        "has_any_analytics": any_analytics,
        "has_purchase_event": events_found["purchase"]["found"],
    }


def check_products(soup, html):
    result = {}
    prices_found = PRICE_PATTERN.findall(html)
    result["sample_prices"] = list(dict.fromkeys(prices_found))[:8]
    product_like = soup.select(PRODUCT_SELECTOR)
    result["approx_product_elements_detected"] = len(product_like)
    result["has_add_to_cart_button"] = bool(re.search(r"add\s?to\s?cart|أضف\s?إلى\s?السلة|اضافة للسلة", html, re.I))
    return result


def _leaf_product_elements(soup):
    """
    يعيد بطاقات المنتجات الفعلية فقط، ويستبعد العناصر الحاوية (مثل شبكة عرض
    المنتجات ككل) التي قد تُطابق نفس الأنماط دون أن تمثل منتجًا واحدًا بعينه،
    وذلك لتقليل الأخطاء وزيادة دقة النتائج.
    """
    raw = soup.select(PRODUCT_SELECTOR)
    return [el for el in raw if not el.select(PRODUCT_SELECTOR)]


def _has_price_signal(el, el_text):
    if PRICE_PATTERN.search(el_text):
        return True
    if el.select_one(PRICE_CLASS_SELECTOR):
        return True
    if el.get("data-price"):
        return True
    return False


def _extract_product_name(el, link, img):
    name = link.get_text(strip=True)
    if name:
        return name
    title_el = el.select_one(TITLE_CLASS_SELECTOR)
    if title_el and title_el.get_text(strip=True):
        return title_el.get_text(strip=True)
    if img:
        alt = (img.get("alt") or img.get("title") or "").strip()
        if alt:
            return alt
    return ""


def find_problem_products(soup, base_url, limit=15):
    """
    يحدد منتجات بعينها تحمل مؤشرات مشكلة واضحة ومؤكدة، مع رابط مباشر لكل
    منتج. يعتمد الفحص على أدلة متعددة قبل تصنيف أي منتج كمتضرر، تجنبًا
    لعرض مشاكل غير حقيقية قد تقلل من مصداقية التقرير.
    """
    product_like = _leaf_product_elements(soup)
    seen_urls = set()
    problems = []

    for el in product_like:
        link = el if el.name == "a" else el.find("a", href=True)
        if not link or not link.get("href"):
            continue
        href = urljoin(base_url, link["href"])
        normalized = href.split("#")[0].rstrip("/")
        if normalized in seen_urls or normalized == base_url.rstrip("/"):
            continue
        seen_urls.add(normalized)

        img = el.find("img")
        name = _extract_product_name(el, link, img)
        el_text = el.get_text(" ", strip=True)
        has_price = _has_price_signal(el, el_text)

        # لا يُعتد بالعنصر كمنتج أصلًا إن لم تتوفر فيه أدنى ملامح البطاقة
        # التجارية (اسم أو صورة على الأقل)، تفاديًا لرصد عناصر ليست منتجات.
        if not name and not img:
            continue

        issues = []
        if not name:
            issues.append("لا يوجد اسم ظاهر لهذا المنتج")
        if not img or not img.get("src"):
            issues.append("لا توجد صورة لهذا المنتج")
        elif not (img.get("alt") or img.get("title") or "").strip():
            issues.append("صورة المنتج بلا نص بديل (alt text)، ما يؤثر سلبًا على الظهور في محركات البحث")
        if not has_price:
            issues.append("لا يظهر سعر محدد بجانب هذا المنتج")

        # يُعتمد المنتج ضمن القائمة فقط إذا توفر دليل قوي واحد على الأقل
        # (غياب الاسم أو غياب الصورة كليًا)، أو دليلان فأكثر مجتمعَين،
        # تقليلًا لاحتمالية الإبلاغ عن مشكلة غير مؤكدة.
        strong_issue = (not name) or (not img or not img.get("src"))
        if issues and (strong_issue or len(issues) >= 2):
            problems.append({"name": name or "(بلا اسم)", "url": href, "issues": issues})

        if len(problems) >= limit:
            break
    return problems


# ==================== مطابقة سياسات إعلانات جوجل ====================
# قواعد استرشادية مبنية على الفئات المعروفة لسياسات إعلانات جوجل للمحتوى الممنوع
# والمقيّد وسياسة الادعاءات المضللة. هذا الفحص استدلالي وليس قرارًا رسميًا من
# جوجل، والهدف منه لفت الانتباه إلى ما يستحق مراجعة يدوية قبل تفعيل الإعلانات.
GOOGLE_POLICY_RULES = [
    ("محتوى ممنوع", r"مسدس|بندقية|ذخيرة|سلاح ناري|متفجرات(?!\s?ألعاب)", "قد يندرج ضمن الأسلحة أو الذخائر أو المتفجرات الممنوعة إعلانيًا"),
    ("محتوى ممنوع", r"مخدرات|حشيش|كوكايين|أدوات تعاطي|بايب تدخين", "قد يتعلق بالمخدرات أو أدوات تعاطيها الممنوعة إعلانيًا"),
    ("محتوى ممنوع", r"تقليد فاخر|نسخة مطابقة للأصلي|replica\s|fake\s?brand|copy\s?original", "قد يوحي بمنتج مقلّد لعلامة تجارية، وهو أمر ممنوع"),
    ("محتوى ممنوع", r"جهاز فك تشفير|بث مقرصن|قنوات مشفرة مجانا|iptv\s?illegal", "قد يتعلق بمحتوى أو أجهزة مقرصنة ممنوعة إعلانيًا"),
    ("محتوى مقيد", r"خمر|نبيذ|فودكا|ويسكي|بيرة(?!\s?شعير\s?خالي)|مشروبات كحولية", "منتجات كحولية تخضع لقيود إعلانية وتتطلب تصريحًا خاصًا"),
    ("محتوى مقيد", r"قمار|يانصيب|مراهنات|كازينو|casino|betting", "محتوى قمار أو مراهنات يتطلب تصريحًا خاصًا من جوجل"),
    ("محتوى مقيد", r"دواء|علاج طبي|صيدلية|روشتة طبية|مكمل غذائي|حبوب تخسيس|supplement", "منتجات صحية أو دوائية تخضع لقيود إعلانية وقد تتطلب تصريحًا خاصًا"),
    ("محتوى مقيد", r"للبالغين فقط|محتوى جنسي|adult\s?content", "محتوى للبالغين يخضع لقيود صارمة في الإعلانات"),
    ("ادعاءات مضللة", r"علاج نهائي|يشفي تماما|معجزة طبية|مضمون 100%|miracle\s?cure|guaranteed\s?cure", "ادعاء صحي أو تسويقي مبالغ فيه قد يخالف سياسة الادعاءات المضللة"),
    ("ادعاءات مضللة", r"الأفضل في العالم|الأرخص على الإطلاق|رقم 1 عالميا|best\s?in\s?the\s?world", "صياغة تفوّق مطلقة دون إثبات قد تُرفض في المراجعة الإعلانية"),
]


def check_google_ads_policy(text):
    """يفحص نصًا (اسم منتج أو وصفه) بحثًا عن مؤشرات مخالفة لسياسات إعلانات جوجل."""
    if not text:
        return []
    flags = []
    for category, pattern, message in GOOGLE_POLICY_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            flags.append(f"{category}: {message}")
    if re.search(r"[!！]{3,}|[؟?]{3,}", text):
        flags.append("تنسيق ترويجي مبالغ فيه: علامات ترقيم متكررة قد تخالف سياسة تنسيق الإعلانات")
    letters_only = re.sub(r"[^A-Za-z]", "", text)
    if len(letters_only) >= 6 and letters_only.isupper():
        flags.append("نص بأحرف إنجليزية كبيرة بالكامل قد يخالف سياسة تنسيق الإعلانات")
    return flags


def find_google_policy_products(soup, base_url, limit=15):
    """يحدد منتجات تحمل مؤشرات مخالفة محتملة لسياسات إعلانات جوجل، مع رابط كل منتج."""
    product_like = _leaf_product_elements(soup)
    seen_urls = set()
    flagged = []

    for el in product_like:
        link = el if el.name == "a" else el.find("a", href=True)
        if not link or not link.get("href"):
            continue
        href = urljoin(base_url, link["href"])
        normalized = href.split("#")[0].rstrip("/")
        if normalized in seen_urls or normalized == base_url.rstrip("/"):
            continue

        img = el.find("img")
        name = _extract_product_name(el, link, img)
        el_text = el.get_text(" ", strip=True)
        flags = check_google_ads_policy(name) or check_google_ads_policy(el_text)
        if flags:
            seen_urls.add(normalized)
            flagged.append({"name": name or "(بلا اسم)", "url": href, "flags": list(dict.fromkeys(flags))})
        if len(flagged) >= limit:
            break
    return flagged


def check_pagespeed(url, api_key):
    if not api_key:
        return {"skipped": True}
    endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {"url": url, "key": api_key, "strategy": "mobile", "category": "performance"}
    try:
        r = requests.get(endpoint, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        score = data["lighthouseResult"]["categories"]["performance"]["score"]
        metrics = data["lighthouseResult"]["audits"]
        return {
            "performance_score": round(score * 100),
            "largest_contentful_paint": metrics.get("largest-contentful-paint", {}).get("displayValue"),
        }
    except Exception as e:
        return {"error": str(e)}


def score_report(seo, ux, pagespeed):
    seo_score = sum([
        20 if seo.get("title_ok") else 0, 20 if seo.get("meta_description_ok") else 0,
        15 if seo.get("h1_ok") else 0, 15 if seo.get("has_structured_data") else 0,
        15 if seo.get("has_open_graph") else 0, 15 if seo.get("sitemap_found") else 0,
    ])
    ux_score = sum([
        30 if ux.get("has_search_box") else 0, 25 if ux.get("has_cart_icon") else 0,
        25 if ux.get("has_whatsapp_or_chat") else 0, 20 if ux.get("uses_https") else 0,
    ])
    return {"seo_score": seo_score, "ux_score": ux_score, "speed_score": pagespeed.get("performance_score")}


def badge(ok):
    return "✅" if ok else "❌"


def build_audit_pdf(full_report):
    seo, ux, products = full_report["seo"], full_report["ux"], full_report["products"]
    scores = full_report["scores"]

    pdf = new_pdf()
    pdf_title(pdf, "تقرير فحص المتجر الإلكتروني", 20)
    pdf.set_font("Arabic", "", 10)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(0, 7, ar(full_report["url"]), align="R")
    pdf.multi_cell(0, 7, ar("تاريخ الفحص: " + full_report["scanned_at"]), align="R")
    pdf.ln(4)

    pdf_subtitle(pdf, f"الدرجات العامة — تحسين محركات البحث: {scores['seo_score']}/100   "
                       f"تجربة المستخدم: {scores['ux_score']}/100   "
                       f"السرعة: {scores['speed_score'] if scores['speed_score'] is not None else '—'}")

    pdf_subtitle(pdf, "تحسين محركات البحث (SEO)")
    pdf_line(pdf, "العنوان", seo["title_ok"], seo["title"] or "غير موجود")
    pdf_line(pdf, "الوصف التعريفي (Meta Description)", seo["meta_description_ok"])
    pdf_line(pdf, f"عنصر H1 (العدد: {seo['h1_count']})", seo["h1_ok"])
    pdf_line(pdf, "بيانات منظّمة (Structured Data)", seo["has_structured_data"])
    pdf_line(pdf, "بطاقات المشاركة (Open Graph)", seo["has_open_graph"])
    pdf_line(pdf, "خريطة الموقع (Sitemap)", seo["sitemap_found"])
    pdf_line(pdf, f"صور بلا نص بديل: {seo['images_missing_alt']} من أصل {seo['total_images']}")

    pdf_subtitle(pdf, "تجربة المستخدم")
    pdf_line(pdf, "بروتوكول HTTPS", ux["uses_https"])
    pdf_line(pdf, "وجود خانة بحث", ux["has_search_box"])
    pdf_line(pdf, "وضوح سلة المشتريات", ux["has_cart_icon"])
    pdf_line(pdf, "وسيلة تواصل مباشرة (واتساب أو محادثة فورية)", ux["has_whatsapp_or_chat"])

    tracking = full_report.get("tracking")
    if tracking:
        pdf_subtitle(pdf, "أدوات تتبع الإعلانات والتحويلات")
        for t in tracking["tools"].values():
            pdf_line(pdf, t["label"], t["found"])
        for e in tracking["events"].values():
            pdf_line(pdf, e["label"], e["found"])
        if not tracking["has_any_ad_tracking"]:
            pdf.set_font("Arabic", "", 10)
            pdf.set_text_color(190, 40, 40)
            pdf.multi_cell(0, 7, ar(
                "تنبيه: لم يُرصد أي كود لأداة تتبع إعلانية. في حال وجود إنفاق إعلاني حالي، "
                "فإن التحويلات على الأرجح لا تُقاس، ما يؤدي إلى إهدار الميزانية الإعلانية."
            ), align="R")
            pdf.set_text_color(20, 20, 20)

    pdf_subtitle(pdf, "المنتجات")
    pdf_line(pdf, f"عدد عناصر المنتجات المكتشفة: {products['approx_product_elements_detected']}")
    pdf_line(pdf, "زر إضافة إلى السلة", products["has_add_to_cart_button"])
    if products["sample_prices"]:
        pdf_line(pdf, "أمثلة على أسعار مرصودة: " + "، ".join(products["sample_prices"]))

    pdf_subtitle(pdf, "الأداء العام")
    pdf_line(pdf, f"زمن الاستجابة: {full_report['response_time_seconds']} ثانية")
    pdf_line(pdf, f"حجم الصفحة: {full_report['page_size_kb']} كيلوبايت")

    problem_products = full_report.get("problem_products") or []
    if problem_products:
        pdf_subtitle(pdf, f"منتجات تحتاج إلى مراجعة وتعديل ({len(problem_products)})")
        for pp in problem_products:
            pdf.set_font("Arabic", "", 11)
            pdf.set_text_color(20, 20, 20)
            pdf.multi_cell(0, 7, ar(pp["name"]), align="R")
            pdf.set_font("Arabic", "", 9)
            pdf.set_text_color(70, 120, 190)
            pdf.multi_cell(0, 6, ar(pp["url"]), align="R")
            for issue in pp["issues"]:
                pdf_line(pdf, issue, False)
            pdf.ln(2)

    policy_products = full_report.get("policy_products") or []
    if policy_products:
        pdf_subtitle(pdf, f"منتجات قد تخالف سياسات إعلانات جوجل ({len(policy_products)})")
        pdf.set_font("Arabic", "", 9)
        pdf.set_text_color(120, 120, 120)
        pdf.multi_cell(0, 6, ar("فحص استدلالي وليس قرارًا رسميًا من جوجل، يُنصح بمراجعة يدوية."), align="R")
        pdf.ln(1)
        for pp in policy_products:
            pdf.set_font("Arabic", "", 11)
            pdf.set_text_color(20, 20, 20)
            pdf.multi_cell(0, 7, ar(pp["name"]), align="R")
            pdf.set_font("Arabic", "", 9)
            pdf.set_text_color(70, 120, 190)
            pdf.multi_cell(0, 6, ar(pp["url"]), align="R")
            for flag in pp["flags"]:
                pdf_line(pdf, flag, False)
            pdf.ln(2)

    return bytes(pdf.output())


# ==================== التبويب الأول: فحص المتجر ====================
def render_audit_tab():
    hero("🔍 أداة فحص المتاجر الإلكترونية",
         "أدخل رابط أي متجر إلكتروني للحصول على تقرير شامل حول تحسين محركات البحث "
         "وتجربة المستخدم والمنتجات خلال ثوانٍ")

    with st.form("audit_form"):
        url = st.text_input("رابط المتجر", placeholder="https://example-store.com")
        api_key = st.text_input("مفتاح PageSpeed API (اختياري، لقياس درجة السرعة)", type="password")
        submitted = st.form_submit_button("✨ فحص المتجر", use_container_width=True, type="primary")

    if submitted:
        if not url.startswith("http"):
            st.error("يرجى إدخال رابط صحيح يبدأ بـ https://")
        else:
            with st.spinner("جارٍ فحص المتجر..."):
                try:
                    html, response_time, page_size = fetch_html(url)
                    soup = BeautifulSoup(html, "html.parser")
                    seo = check_seo(soup, url)
                    ux = check_ux(soup, html, url)
                    products = check_products(soup, html)
                    problem_products = find_problem_products(soup, url)
                    policy_products = find_google_policy_products(soup, url)
                    tracking = check_tracking_tools(html)
                    pagespeed = check_pagespeed(url, api_key)
                    scores = score_report(seo, ux, pagespeed)
                except requests.RequestException as e:
                    st.error(f"تعذّر الوصول إلى الرابط: {e}")
                    st.stop()

            st.success("تم الفحص بنجاح ✅")

            gauge_row([
                ("تحسين محركات البحث", scores['seo_score']),
                ("تجربة المستخدم", scores['ux_score']),
                ("السرعة", scores['speed_score']),
            ])

            section_eyebrow("النتائج التفصيلية")
            st.markdown(f"""
            <div class="section-card">
                <h3>🔍 تحسين محركات البحث (SEO)</h3>
                {pill(seo['title_ok'], 'العنوان: ' + (seo['title'] or 'غير موجود'))}
                {pill(seo['meta_description_ok'], 'الوصف التعريفي')}
                {pill(seo['h1_ok'], f"عنصر H1 (العدد: {seo['h1_count']})")}
                {pill(seo['has_structured_data'], 'بيانات منظّمة')}
                {pill(seo['has_open_graph'], 'بطاقات المشاركة')}
                {pill(seo['sitemap_found'], 'خريطة الموقع')}
                <p style="color:#9aa4b2; margin-top:0.8rem;">🖼️ صور بلا نص بديل: {seo['images_missing_alt']} من أصل {seo['total_images']}</p>
            </div>

            <div class="section-card">
                <h3>🎨 تجربة المستخدم</h3>
                {pill(ux['uses_https'], 'بروتوكول HTTPS')}
                {pill(ux['has_search_box'], 'خانة بحث')}
                {pill(ux['has_cart_icon'], 'سلة مشتريات واضحة')}
                {pill(ux['has_whatsapp_or_chat'], 'وسيلة تواصل مباشرة')}
            </div>
            """, unsafe_allow_html=True)

            section_eyebrow("الإعلانات والتحويلات")
            tools_pills = "".join(pill(t["found"], t["label"]) for t in tracking["tools"].values())
            events_pills = "".join(pill(e["found"], e["label"]) for e in tracking["events"].values())
            tracking_border = "rgba(231,76,60,0.35)" if not tracking["has_any_ad_tracking"] else "rgba(212,175,55,0.18)"
            tracking_title_color = "#e74c3c" if not tracking["has_any_ad_tracking"] else "#d4af37"

            st.markdown(f"""
            <div class="section-card" style="border-color: {tracking_border};">
                <h3 style="color:{tracking_title_color};">📊 أدوات تتبع الإعلانات والتحويلات</h3>
                <p style="color:#9aa4b2; margin-top:0; margin-bottom:0.8rem;">أدوات التتبع المكتشفة في كود الصفحة:</p>
                {tools_pills}
                <p style="color:#9aa4b2; margin-top:1rem; margin-bottom:0.5rem;">أحداث التحويل المكتشفة:</p>
                {events_pills}
            </div>
            """, unsafe_allow_html=True)

            if not tracking["has_any_ad_tracking"]:
                st.error(
                    "⚠️ لم يُرصد أي كود لأداة تتبع إعلانية (إعلانات جوجل، ميتا، تيك توك، سناب شات) على الصفحة. "
                    "في حال كان المتجر يُنفق ميزانية إعلانية حاليًا، فهذا يعني على الأرجح أن التحويلات لا تُقاس، "
                    "ما يجعل تحسين الحملات الإعلانية غير ممكن ويؤدي إلى إهدار الميزانية دون معرفة السبب."
                )
            elif not tracking["has_purchase_event"]:
                st.warning(
                    "⚠️ توجد أداة تتبع مركّبة، لكن لم يُرصد حدث إتمام الشراء (Purchase) بشكل صريح في كود الصفحة. "
                    "قد يكون هذا الحدث مفعّلًا من صفحة تأكيد الطلب فقط، لذا يُنصح بالتأكد يدويًا من أن قيمة "
                    "المبيعات الفعلية تصل بشكل صحيح إلى حسابات الإعلانات."
                )

            st.markdown(f"""
            <div class="section-card">
                <h3>🛒 المنتجات</h3>
                <p style="color:#c9d1d9;">عدد عناصر المنتجات المكتشفة: <b>{products['approx_product_elements_detected']}</b></p>
                {pill(products['has_add_to_cart_button'], 'زر إضافة إلى السلة')}
                <p style="color:#9aa4b2; margin-top:0.8rem;">{'أمثلة على أسعار مرصودة: ' + '، '.join(products['sample_prices']) if products['sample_prices'] else ''}</p>
            </div>
            """, unsafe_allow_html=True)

            section_eyebrow("المنتجات التي تحتاج إلى مراجعة")
            if problem_products:
                st.markdown(f"""
                <div class="section-card">
                    <h3>🔗 منتجات تحتاج إلى مراجعة وتعديل ({len(problem_products)})</h3>
                    <p style="color:#9aa4b2;">فيما يلي روابط مباشرة لمنتجات ظهرت عليها مؤشرات مشكلة مؤكدة، لتسهيل الوصول إليها ومراجعتها.</p>
                </div>
                """, unsafe_allow_html=True)
                for pp in problem_products:
                    with st.expander(f"⚠️ {pp['name']}"):
                        st.markdown(f"🔗 [فتح صفحة المنتج]({pp['url']})")
                        for issue in pp["issues"]:
                            st.write(f"❌ {issue}")
            else:
                st.markdown("""
                <div class="section-card">
                    <h3>🔗 منتجات تحتاج إلى مراجعة وتعديل</h3>
                    <p style="color:#2ecc71;">لم يُرصد أي منتج يحمل مؤشرات مشكلة مؤكدة ضمن العناصر التي أمكن تحليلها.</p>
                </div>
                """, unsafe_allow_html=True)

            if policy_products:
                st.markdown(f"""
                <div class="section-card" style="border-color: rgba(231,76,60,0.35);">
                    <h3 style="color:#e74c3c;">🚫 منتجات قد تخالف سياسات إعلانات جوجل ({len(policy_products)})</h3>
                    <p style="color:#9aa4b2;">فحص استدلالي مبني على فئات سياسات إعلانات جوجل المعروفة (محتوى ممنوع،
                    محتوى مقيّد، ادعاءات تسويقية مبالغ فيها). هذا الفحص لا يمثل قرارًا رسميًا من جوجل، ويُنصح
                    بمراجعة يدوية لكل منتج قبل اتخاذ أي إجراء.</p>
                </div>
                """, unsafe_allow_html=True)
                for pp in policy_products:
                    with st.expander(f"🚫 {pp['name']}"):
                        st.markdown(f"🔗 [فتح صفحة المنتج]({pp['url']})")
                        for flag in pp["flags"]:
                            st.write(f"⚠️ {flag}")
            else:
                st.markdown("""
                <div class="section-card">
                    <h3>🚫 منتجات قد تخالف سياسات إعلانات جوجل</h3>
                    <p style="color:#2ecc71;">لم تُرصد مؤشرات مخالفة واضحة ضمن العناصر التي أمكن تحليلها.</p>
                </div>
                """, unsafe_allow_html=True)

            st.markdown(f"""
            <div class="section-card">
                <h3>⏱️ الأداء العام</h3>
                <p style="color:#c9d1d9;">زمن الاستجابة: <b>{response_time:.2f}</b> ثانية &nbsp;|&nbsp; حجم الصفحة: <b>{page_size/1024:.1f}</b> كيلوبايت</p>
            </div>
            """, unsafe_allow_html=True)

            full_report = {
                "url": url, "scanned_at": datetime.utcnow().isoformat() + "Z",
                "response_time_seconds": round(response_time, 2), "page_size_kb": round(page_size / 1024, 1),
                "scores": scores, "seo": seo, "ux": ux, "products": products, "pagespeed": pagespeed,
                "problem_products": problem_products, "policy_products": policy_products,
                "tracking": tracking,
            }

            pdf_bytes = build_audit_pdf(full_report)
            col_pdf, col_json = st.columns(2)
            col_pdf.download_button(
                "📄 تحميل التقرير بصيغة PDF",
                data=pdf_bytes,
                file_name="store_report.pdf",
                mime="application/pdf",
                use_container_width=True,
                type="primary",
            )
            col_json.download_button(
                "⬇️ تحميل البيانات الخام (JSON)",
                data=json.dumps(full_report, ensure_ascii=False, indent=2),
                file_name="store_report.json",
                mime="application/json",
                use_container_width=True,
            )


# ==================== التبويب الثاني: تعديل منتجات سلة ====================
SALLA_AUTH_URL = "https://accounts.salla.sa/oauth2/auth"
SALLA_TOKEN_URL = "https://accounts.salla.sa/oauth2/token"
SALLA_API_BASE = "https://api.salla.dev/admin/v2"


def salla_headers():
    return {"Authorization": f"Bearer {st.session_state['salla_token']}"}


def salla_exchange_code(client_id, client_secret, redirect_uri, code):
    resp = requests.post(SALLA_TOKEN_URL, data={
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "code": code,
    }, timeout=20)
    resp.raise_for_status()
    return resp.json()


def salla_get_products(page=1):
    resp = requests.get(f"{SALLA_API_BASE}/products", headers=salla_headers(),
                         params={"page": page, "per_page": 20}, timeout=20)
    resp.raise_for_status()
    return resp.json()


def salla_update_product(product_id, payload):
    resp = requests.put(f"{SALLA_API_BASE}/products/{product_id}", headers=salla_headers(),
                         json=payload, timeout=20)
    resp.raise_for_status()
    return resp.json()


def analyze_product_issues(p):
    """
    يفحص بيانات منتج فعلي من متجر سلة (عبر واجهة برمجة التطبيقات الموثوقة)
    ويحدد مشكلاته بدقة، اعتمادًا على بيانات مؤكدة وليس تخمينًا.
    """
    issues = []
    name = (p.get("name") or "").strip()
    if not name:
        issues.append("لا يوجد اسم لهذا المنتج")
    elif len(name) < 8:
        issues.append("اسم المنتج قصير جدًا (أقل من 8 أحرف)")

    desc = (p.get("description") or "").strip()
    if not desc:
        issues.append("لا يوجد وصف لهذا المنتج")
    elif len(re.sub("<[^>]+>", "", desc)) < 30:
        issues.append("وصف المنتج قصير جدًا وغير كافٍ")

    price = (p.get("price") or {}).get("amount")
    if not price or price == 0:
        issues.append("السعر غير محدد أو يساوي صفرًا")

    qty = p.get("quantity")
    if p.get("unlimited_quantity") is False and (qty is None or qty == 0):
        issues.append("الكمية المتاحة صفر (المنتج غير متوفر)")

    images = p.get("images") or []
    if not images:
        issues.append("لا توجد صور لهذا المنتج")

    if not p.get("categories"):
        issues.append("المنتج غير مرتبط بأي تصنيف")

    if p.get("status") and p.get("status") != "sale":
        issues.append(f"حالة المنتج الحالية: {p.get('status')} (غير معروض للبيع)")

    return issues


def analyze_salla_policy(p):
    """يفحص اسم المنتج ووصفه في سلة بحثًا عن مؤشرات مخالفة لسياسات إعلانات جوجل."""
    name = (p.get("name") or "")
    desc = re.sub("<[^>]+>", " ", p.get("description") or "")
    combined = f"{name} {desc}"
    return list(dict.fromkeys(check_google_ads_policy(combined)))


def build_products_issues_pdf(products_with_issues):
    pdf = new_pdf()
    pdf_title(pdf, "تقرير المنتجات التي تحتاج إلى تعديل", 18)
    pdf.set_font("Arabic", "", 10)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(0, 7, ar(f"عدد المنتجات: {len(products_with_issues)}"), align="R")
    pdf.ln(3)
    for p, issues in products_with_issues:
        pdf_subtitle(pdf, p.get("name") or "(بلا اسم)")
        for issue in issues:
            pdf_line(pdf, issue, False)
        pdf.ln(2)
    return bytes(pdf.output())


def build_policy_products_pdf(products_with_flags):
    pdf = new_pdf()
    pdf_title(pdf, "منتجات قد تخالف سياسات إعلانات جوجل", 18)
    pdf.set_font("Arabic", "", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(0, 6, ar("فحص استدلالي وليس قرارًا رسميًا من جوجل، يُنصح بمراجعة يدوية."), align="R")
    pdf.ln(3)
    for p, flags in products_with_flags:
        pdf_subtitle(pdf, p.get("name") or "(بلا اسم)")
        for flag in flags:
            pdf_line(pdf, flag, False)
        pdf.ln(2)
    return bytes(pdf.output())


def render_salla_tab():
    hero("🛠️ ربط منصة سلة وتعديل المنتجات",
         "اربط متجرك على منصة سلة لتتمكن من تعديل أسماء المنتجات وأسعارها وكمياتها مباشرة من هذه الصفحة")

    if "salla_token" not in st.session_state:
        st.session_state["salla_token"] = None

    query_code = st.query_params.get("code")

    with st.expander("⚙️ إعدادات التطبيق (تُضبط مرة واحدة فقط)", expanded=not st.session_state["salla_token"]):
        st.markdown(
            "يلزم إنشاء تطبيق على [منصة سلة للمطورين](https://salla.partners) أولًا، "
            "والحصول منه على Client ID و Client Secret، ثم تحديد رابط هذا الموقع كـ Redirect URI."
        )
        client_id = st.text_input("Client ID", value=st.session_state.get("salla_client_id", ""))
        client_secret = st.text_input("Client Secret", type="password",
                                       value=st.session_state.get("salla_client_secret", ""))
        redirect_uri = st.text_input("Redirect URI (رابط هذا الموقع)",
                                      value=st.session_state.get("salla_redirect_uri", ""))
        st.session_state["salla_client_id"] = client_id
        st.session_state["salla_client_secret"] = client_secret
        st.session_state["salla_redirect_uri"] = redirect_uri

        if client_id and redirect_uri:
            auth_link = (
                f"{SALLA_AUTH_URL}?client_id={client_id}&response_type=code"
                f"&redirect_uri={redirect_uri}&scope=offline_access%20products.read_write"
            )
            st.link_button("🔗 ربط متجر سلة الآن", auth_link, use_container_width=True)

    if query_code and not st.session_state["salla_token"]:
        cid = st.session_state.get("salla_client_id")
        cs = st.session_state.get("salla_client_secret")
        ruri = st.session_state.get("salla_redirect_uri")
        if cid and cs and ruri:
            try:
                token_data = salla_exchange_code(cid, cs, ruri, query_code)
                st.session_state["salla_token"] = token_data.get("access_token")
                st.query_params.clear()
                st.success("✅ تم ربط المتجر بنجاح")
            except requests.RequestException as e:
                st.error(f"فشل استبدال الرمز بالتوكن: {e}")
        else:
            st.warning("تم استلام رمز التفويض من سلة، لكن يلزم إدخال Client ID وSecret وRedirect URI أولًا ثم الضغط على رابط الربط مجددًا")

    if not st.session_state["salla_token"]:
        st.info("لا يوجد متجر مرتبط حاليًا. افتح الإعدادات أعلاه واضغط رابط الربط.")
        return

    st.success("المتجر مرتبط ✅")
    if st.button("إلغاء الربط"):
        st.session_state["salla_token"] = None
        st.rerun()

    if st.button("🔄 جلب المنتجات", type="primary"):
        with st.spinner("جارٍ جلب المنتجات..."):
            try:
                data = salla_get_products()
                st.session_state["salla_products"] = data.get("data", [])
            except requests.RequestException as e:
                st.error(f"تعذّر جلب المنتجات: {e}")

    products = st.session_state.get("salla_products", [])
    if products:
        products_issues = [(p, analyze_product_issues(p)) for p in products]
        need_fix = [(p, issues) for p, issues in products_issues if issues]

        st.markdown(f"### ⚠️ منتجات تحتاج إلى تعديل ({len(need_fix)} من أصل {len(products)})")
        if not need_fix:
            st.success("جميع المنتجات سليمة، لم تُرصد أي مشكلة 🎉")
        else:
            st.download_button(
                "📄 تحميل تقرير المنتجات التي تحتاج إلى تعديل بصيغة PDF",
                data=build_products_issues_pdf(need_fix),
                file_name="products_need_fix.pdf",
                mime="application/pdf",
            )
            for p, issues in need_fix:
                with st.expander(f"⚠️ {p.get('name') or '(بلا اسم)'} — {len(issues)} مشكلة"):
                    for issue in issues:
                        st.write(f"❌ {issue}")
                    st.divider()
                    new_name = st.text_input("الاسم", value=p.get("name", ""), key=f"issue_name_{p['id']}")
                    current_price = (p.get("price") or {}).get("amount", 0) or 0
                    new_price = st.number_input("السعر", value=float(current_price), key=f"issue_price_{p['id']}")
                    new_qty = st.number_input("الكمية المتاحة", value=int(p.get("quantity", 0) or 0),
                                               key=f"issue_qty_{p['id']}")
                    if st.button("💾 حفظ التعديل", key=f"issue_save_{p['id']}"):
                        try:
                            salla_update_product(p["id"], {
                                "name": new_name, "price": new_price, "quantity": new_qty,
                            })
                            st.success("تم الحفظ ✅")
                        except requests.RequestException as e:
                            st.error(f"فشل الحفظ: {e}")

        st.markdown(f"### 🗂️ جميع المنتجات ({len(products)})")
        for p, issues in products_issues:
            mark = "⚠️ " if issues else "✅ "
            with st.expander(f"{mark}{p.get('name')} — {p.get('price', {}).get('amount', '')} {p.get('price', {}).get('currency', '')}"):
                new_name = st.text_input("الاسم", value=p.get("name", ""), key=f"name_{p['id']}")
                current_price = p.get("price", {}).get("amount", 0)
                new_price = st.number_input("السعر", value=float(current_price), key=f"price_{p['id']}")
                new_qty = st.number_input("الكمية المتاحة", value=int(p.get("quantity", 0) or 0),
                                           key=f"qty_{p['id']}")
                if st.button("💾 حفظ التعديل", key=f"save_{p['id']}"):
                    try:
                        salla_update_product(p["id"], {
                            "name": new_name, "price": new_price, "quantity": new_qty,
                        })
                        st.success("تم الحفظ ✅")
                    except requests.RequestException as e:
                        st.error(f"فشل الحفظ: {e}")

        products_policy = [(p, analyze_salla_policy(p)) for p in products]
        policy_flagged = [(p, flags) for p, flags in products_policy if flags]

        st.markdown(f"### 🚫 منتجات مرفوضة من قبل سياسات إعلانات جوجل ({len(policy_flagged)} من أصل {len(products)})")
        st.caption("فحص استدلالي مبني على فئات سياسات إعلانات جوجل المعروفة، وليس قرارًا رسميًا من جوجل. يُنصح بمراجعة يدوية لكل منتج قبل اتخاذ أي إجراء.")
        if not policy_flagged:
            st.success("لم تُرصد مؤشرات مخالفة واضحة ضمن أسماء المنتجات وأوصافها 🎉")
        else:
            st.download_button(
                "📄 تحميل تقرير المنتجات المرفوضة من قبل سياسات جوجل بصيغة PDF",
                data=build_policy_products_pdf(policy_flagged),
                file_name="google_policy_flagged_products.pdf",
                mime="application/pdf",
            )
            for p, flags in policy_flagged:
                with st.expander(f"🚫 {p.get('name') or '(بلا اسم)'} — {len(flags)} مؤشر"):
                    for flag in flags:
                        st.write(f"⚠️ {flag}")


# ==================== نقطة البداية ====================
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 0.6rem 0 1.2rem;">
        <div style="font-size:2.2rem;">🛍️</div>
        <div style="color:#d4af37; font-weight:800; font-size:1.1rem;">أداة فحص المتاجر</div>
        <div style="color:#6b7280; font-size:0.8rem; margin-top:0.2rem;">تقارير احترافية جاهزة للعملاء</div>
    </div>
    <hr style="margin: 0.4rem 0 1rem;">
    """, unsafe_allow_html=True)
    st.markdown("""
    <div style="color:#9aa4b2; font-size:0.85rem; line-height:1.9;">
    <b style="color:#d4af37;">🔍 فحص المتجر</b><br>
    تحليل شامل لأي رابط متجر: SEO، تجربة المستخدم، تتبع الإعلانات،
    ومطابقة سياسات جوجل.<br><br>
    <b style="color:#d4af37;">🛠️ تعديل منتجات سلة</b><br>
    ربط مباشر بمتجر سلة لتعديل المنتجات ورصد ما يحتاج مراجعة.
    </div>
    """, unsafe_allow_html=True)

tab1, tab2 = st.tabs(["🔍 فحص المتجر", "🛠️ تعديل منتجات سلة"])
with tab1:
    render_audit_tab()
with tab2:
    render_salla_tab()
