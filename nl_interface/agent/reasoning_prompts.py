#!/usr/bin/env python3
"""
Reasoning prompts for the Kubernetes Agent.
"""

# Template string with placeholders
REASONING_SUMMARY_PROMPT = """Based on your recent action and its result, provide a brief reasoning summary.

Recent context:
{context_text}

Last action: {last_function}
Result: {last_result_preview}

Provide a 2-3 sentence summary covering:
1. What you learned from this action. Add important details in one sentence.
2. Why this action was important for your objective  
3. What you plan to do next

Keep it concise and focused on operational reasoning."""

def get_reasoning_summary_prompt(context_text: str, last_function: str, last_result_preview: str) -> str:
    return REASONING_SUMMARY_PROMPT.format(
        context_text=context_text,
        last_function=last_function,
        last_result_preview=last_result_preview
    ) 