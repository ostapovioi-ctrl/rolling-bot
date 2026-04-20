def generate_progress_bar(filled, total, style="█▒"):
    if style == "█▒":
        return f"{'█' * filled}{'▒' * (total - filled)}"
    elif style == "🟩⬜":
        return f"{'🟩' * filled}{'⬜' * (total - filled)}"
    elif style == "●○":
        return f"{'●' * filled}{'○' * (total - filled)}"
    elif style == "★☆":
        return f"{'★' * filled}{'☆' * (total - filled)}"
    else:
        return f"{filled}/{total}"