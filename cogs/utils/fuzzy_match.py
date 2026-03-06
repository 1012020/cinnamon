"""Fuzzy command matching for 'Did you mean?' suggestions"""

from difflib import SequenceMatcher
from typing import List, Optional, Tuple


def get_similarity(a: str, b: str) -> float:
    """Calculate similarity ratio between two strings (0.0 to 1.0)"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def find_similar_commands(input_cmd: str, valid_commands: List[str], threshold: float = 0.6, max_suggestions: int = 3) -> List[str]:
    """
    Find similar command names based on fuzzy matching.
    
    Args:
        input_cmd: The command that was entered
        valid_commands: List of valid command names
        threshold: Minimum similarity ratio (0.0 to 1.0)
        max_suggestions: Maximum number of suggestions to return
    
    Returns:
        List of similar command names, sorted by similarity
    """
    if not input_cmd or not valid_commands:
        return []
    
    # Calculate similarity scores
    similarities = []
    for cmd in valid_commands:
        ratio = get_similarity(input_cmd, cmd)
        if ratio >= threshold:
            similarities.append((cmd, ratio))
    
    # Sort by similarity (highest first) and return top matches
    similarities.sort(key=lambda x: x[1], reverse=True)
    return [cmd for cmd, _ in similarities[:max_suggestions]]


def get_suggestion_message(input_cmd: str, suggestions: List[str]) -> str:
    """
    Create a formatted suggestion message.
    
    Args:
        input_cmd: The command that was entered
        suggestions: List of suggested command names
    
    Returns:
        Formatted suggestion message
    """
    if not suggestions:
        return f"command '!{input_cmd}' not found. type !help to see all commands."
    
    if len(suggestions) == 1:
        return f"command '!{input_cmd}' not found. did you mean **!{suggestions[0]}**?"
    
    suggestion_list = ", ".join([f"**!{cmd}**" for cmd in suggestions])
    return f"command '!{input_cmd}' not found. did you mean: {suggestion_list}?"


def check_typos(word: str, valid_words: List[str]) -> Optional[str]:
    """
    Check for common typos (single character edits).
    Returns the first valid match found, or None.
    """
    word = word.lower()
    
    for valid in valid_words:
        valid_lower = valid.lower()
        
        # Check if one character difference
        if len(word) == len(valid_lower):
            diff_count = sum(1 for a, b in zip(word, valid_lower) if a != b)
            if diff_count == 1:
                return valid
        
        # Check if one character missing
        if len(word) == len(valid_lower) - 1:
            for i in range(len(valid_lower)):
                if valid_lower[:i] + valid_lower[i+1:] == word:
                    return valid
        
        # Check if one extra character
        if len(word) == len(valid_lower) + 1:
            for i in range(len(word)):
                if word[:i] + word[i+1:] == valid_lower:
                    return valid
    
    return None


def find_best_match(input_cmd: str, valid_commands: List[str]) -> Tuple[Optional[str], List[str]]:
    """
    Find the best match for a command, checking typos first, then fuzzy matching.
    
    Returns:
        Tuple of (exact_typo_match, fuzzy_suggestions)
    """
    # First check for common typos (single edit distance)
    typo_match = check_typos(input_cmd, valid_commands)
    
    # Then get fuzzy matches
    fuzzy_matches = find_similar_commands(input_cmd, valid_commands, threshold=0.55, max_suggestions=3)
    
    # If typo match exists and isn't in fuzzy matches, prioritize it
    if typo_match and typo_match not in fuzzy_matches:
        fuzzy_matches = [typo_match] + fuzzy_matches[:2]
    
    return (typo_match, fuzzy_matches)
