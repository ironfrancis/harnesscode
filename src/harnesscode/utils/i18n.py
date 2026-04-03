#!/usr/bin/env python3
"""HarnessCode internationalization (i18n) module.

Provides translation support for user-facing CLI messages.
Log messages and code comments remain in English.
"""

import json
import os
from pathlib import Path

# Current language (default: en)
_current_language = "en"

# Translation cache
_translations = {}


def get_locales_dir() -> Path:
    """Return the locales directory path."""
    return Path(__file__).parent.parent / "locales"


def set_language(lang: str) -> str:
    """Set the current language.
    
    Args:
        lang: Language code ('en' or 'zh')
        
    Returns:
        The language code that was set
    """
    global _current_language
    if lang in ("en", "zh", "zh-CN"):
        _current_language = "zh" if lang.startswith("zh") else "en"
    return _current_language


def get_language() -> str:
    """Get the current language code."""
    return _current_language


def load_translations(lang: str = None) -> dict:
    """Load translations for the specified language.
    
    Args:
        lang: Language code (uses current language if None)
        
    Returns:
        Dictionary of translations
    """
    if lang is None:
        lang = _current_language
    
    if lang in _translations:
        return _translations[lang]
    
    locales_dir = get_locales_dir()
    lang_file = locales_dir / f"{lang}.json"
    
    if not lang_file.exists():
        # Fallback to English
        lang_file = locales_dir / "en.json"
    
    try:
        with open(lang_file, "r", encoding="utf-8") as f:
            _translations[lang] = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[i18n] Warning: Failed to load translations for {lang}: {e}")
        _translations[lang] = {}
    
    return _translations[lang]


def t(key: str, lang: str = None) -> str:
    """Get translation for a key.
    
    Args:
        key: Translation key (supports dot notation like 'cli.help.usage')
        lang: Language code (uses current language if None)
        
    Returns:
        Translated string, or the key itself if not found
    """
    if lang is None:
        lang = _current_language
    
    translations = load_translations(lang)
    
    # Support dot notation for nested keys
    keys = key.split(".")
    value = translations
    
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            # Key not found, return the key itself
            return key
    
    return value if isinstance(value, str) else key


def T(key: str, lang: str = None, **kwargs) -> str:
    """Get translation with format string substitution.
    
    Args:
        key: Translation key
        lang: Language code
        **kwargs: Format string arguments
        
    Returns:
        Formatted translated string
    """
    template = t(key, lang)
    if kwargs and "{" in template:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template
    return template


def get_available_languages() -> list:
    """Get list of available languages.
    
    Returns:
        List of language codes
    """
    locales_dir = get_locales_dir()
    if not locales_dir.exists():
        return ["en"]
    
    languages = []
    for file in locales_dir.glob("*.json"):
        lang_code = file.stem
        languages.append(lang_code)
    
    return sorted(languages) if languages else ["en"]
