"""Prospective complete-answer SFT encoding; never rewrites historical masks."""


def causal_example(prompt, completion, *, pad_token_id, maximum_tokens, padded_tokens=None):
    """Unshifted labels for a causal LM: it shifts once inside its loss function."""
    if not prompt or not completion:
        raise ValueError('nonempty prompt and completion required')
    if any(type(token) is not int or token < 0 for token in [*prompt, *completion]):
        raise ValueError('nonnegative integer token IDs required')
    length = len(prompt) + len(completion)
    padded_tokens = length if padded_tokens is None else padded_tokens
    if type(padded_tokens) is not int or not length <= padded_tokens <= maximum_tokens:
        raise ValueError('sequence overflow; truncation is forbidden')
    if type(pad_token_id) is not int or pad_token_id < 0:
        raise ValueError('explicit padding token required')
    padding = padded_tokens - length
    return {'input_ids': [*prompt, *completion, *([pad_token_id] * padding)],
            'attention_mask': [1] * length + [0] * padding,
            'labels': [-100] * len(prompt) + list(completion) + [-100] * padding}


def full_completion_example(tokenizer, messages, answer, *, eos_token_ids,
                            maximum_tokens=3072, padded_tokens=None):
    """Use the complete chat template to establish the assistant token boundary.

    Stop at its first generation terminal. Only whitespace may follow it. This
    prevents an arbitrary hard-coded EOS or a separately encoded boundary from
    silently changing the training target. No answer-token subsampling occurs.
    """
    if not isinstance(answer, str) or not answer or answer != answer.strip():
        raise ValueError('nonempty canonical answer without boundary whitespace required')
    if not messages or messages[-1].get('role') != 'user':
        raise ValueError('a user-ended prompt is required')
    if not eos_token_ids or any(type(x) is not int or x < 0 for x in eos_token_ids):
        raise ValueError('explicit generation terminal IDs required')
    options = dict(tokenize=True, return_dict=True, enable_thinking=False,
                   truncation=False, padding=False)
    prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True,
                                           **options)['input_ids']
    full = tokenizer.apply_chat_template(
        [*messages, {'role': 'assistant', 'content': answer}],
        add_generation_prompt=False, **options)['input_ids']
    if full[:len(prompt)] != prompt:
        raise ValueError('assistant template does not preserve the generation prefix')
    suffix = full[len(prompt):]
    terminal = next((i for i, token in enumerate(suffix) if token in eos_token_ids), None)
    if terminal is None:
        raise ValueError('assistant completion has no generation terminal')
    decode = dict(skip_special_tokens=False, clean_up_tokenization_spaces=False)
    if tokenizer.decode(suffix[:terminal], **decode) != answer:
        raise ValueError('assistant template changes the answer or adds a control prefix')
    if tokenizer.decode(suffix[terminal + 1:], **decode).strip():
        raise ValueError('non-whitespace content follows the assistant terminal')
    completion = suffix[:terminal + 1]
    result = causal_example(prompt, completion, pad_token_id=tokenizer.pad_token_id,
                            maximum_tokens=maximum_tokens, padded_tokens=padded_tokens)
    return dict(result, prompt_tokens=len(prompt), completion_tokens=len(completion),
                terminal_token_id=completion[-1])
