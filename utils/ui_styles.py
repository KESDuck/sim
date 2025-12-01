"""
UI Stylesheet Utilities
=======================
Centralized stylesheet definitions for consistent UI styling across the application.
"""

# Color Palette
COLORS = {
    'blue': '#4A9EFF',
    'blue_dark': '#2A5F8F',
    'blue_light': '#6BB6FF',
    'blue_hover': '#3A7FAF',
    
    'orange': '#FFA500',
    
    'red': '#FF6B6B',
    'red_light': '#FF8B8B',
    'red_dark': '#5A2A2A',
    'red_hover': '#6A3A3A',
    
    'purple': '#9B59B6',
    'purple_light': '#B07CC6',
    'purple_hover': '#AB69C6',
    
    'cyan': '#00CED1',
    
    'green': '#4CAF50',
    'green_dark': '#2A6F2A',
    'green_light': '#6BCF6B',
    'green_hover': '#3A8F3A',
    
    'green_speed': '#4A9F4A',
    'green_speed_dark': '#2A5F2A',
    'green_speed_light': '#6BBF6B',
    'green_speed_hover': '#3A7F3A',
    
    'gray': '#5A5A5A',
    'gray_light': '#6A6A6A',
    'gray_border': '#777',
    'gray_muted': '#B0B0B0',
    'gray_dark': '#555',
    'gray_bg': '#2A2A2A',
    'gray_bg_dark': '#2b2b2b',
    
    'brown': '#8B5A2B',
    'brown_light': '#9B6A3B',
    'brown_border': '#A67C52',
    
    'brown_capture': '#8B4513',
    'brown_capture_light': '#9B5523',
    'brown_capture_border': '#A0522D',
    
    'text_light': '#E0E0E0',
    'white': 'white',
}

def group_box_primary(color: str) -> str:
    """Style for primary group boxes with colored borders"""
    return f"""
        QGroupBox {{
            font-weight: bold;
            color: {color};
            border: 2px solid {color};
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }}
    """

def group_box_secondary() -> str:
    """Style for secondary/nested group boxes"""
    return f"""
        QGroupBox {{
            color: {COLORS['gray_muted']};
            border: 1px solid {COLORS['gray_dark']};
            border-radius: 3px;
            margin-top: 5px;
            padding-top: 5px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }}
    """

def label_muted() -> str:
    """Style for muted labels"""
    return f"color: {COLORS['gray_muted']};"

def button_toggle_blue() -> str:
    """Style for blue toggle buttons (frame type buttons)"""
    return f"""
        QPushButton {{
            background-color: {COLORS['blue_dark']};
            color: {COLORS['white']};
            border: 2px solid {COLORS['blue']};
            border-radius: 4px;
            padding: 5px;
        }}
        QPushButton:checked {{
            background-color: {COLORS['blue']};
            border: 2px solid {COLORS['blue_light']};
        }}
        QPushButton:hover {{
            background-color: {COLORS['blue_hover']};
        }}
    """

def button_toggle_green() -> str:
    """Style for green toggle buttons (display options)"""
    return f"""
        QPushButton {{
            background-color: {COLORS['green_dark']};
            color: {COLORS['white']};
            border: 2px solid {COLORS['green']};
            border-radius: 4px;
            padding: 5px;
        }}
        QPushButton:checked {{
            background-color: {COLORS['green']};
            border: 2px solid {COLORS['green_light']};
        }}
        QPushButton:hover {{
            background-color: {COLORS['green_hover']};
        }}
    """

def button_toggle_green_speed() -> str:
    """Style for green speed toggle buttons"""
    return f"""
        QPushButton {{
            background-color: {COLORS['green_speed_dark']};
            color: {COLORS['white']};
            border: 2px solid {COLORS['green_speed']};
            border-radius: 4px;
            padding: 5px;
        }}
        QPushButton:checked {{
            background-color: {COLORS['green_speed']};
            border: 2px solid {COLORS['green_speed_light']};
        }}
        QPushButton:hover {{
            background-color: {COLORS['green_speed_hover']};
        }}
    """

def button_action() -> str:
    """Style for standard action buttons (gray)"""
    return f"""
        QPushButton {{
            background-color: {COLORS['gray']};
            color: {COLORS['white']};
            border: 1px solid {COLORS['gray_border']};
            border-radius: 4px;
            padding: 5px;
        }}
        QPushButton:hover {{
            background-color: {COLORS['gray_light']};
        }}
    """

def button_save() -> str:
    """Style for save button (brown)"""
    return f"""
        QPushButton {{
            background-color: {COLORS['brown']};
            color: {COLORS['white']};
            border: 1px solid {COLORS['brown_border']};
            border-radius: 4px;
            padding: 5px;
        }}
        QPushButton:hover {{
            background-color: {COLORS['brown_light']};
        }}
    """

def button_capture() -> str:
    """Style for capture button (dark brown)"""
    return f"""
        QPushButton {{
            background-color: {COLORS['brown_capture']};
            color: {COLORS['white']};
            border: 1px solid {COLORS['brown_capture_border']};
            border-radius: 4px;
            padding: 5px;
        }}
        QPushButton:hover {{
            background-color: {COLORS['brown_capture_light']};
        }}
    """

def button_motor() -> str:
    """Style for motor toggle button (red)"""
    return f"""
        QPushButton {{
            background-color: {COLORS['red_dark']};
            color: {COLORS['white']};
            border: 2px solid {COLORS['red']};
            border-radius: 4px;
            padding: 8px;
            font-weight: bold;
        }}
        QPushButton:checked {{
            background-color: {COLORS['red']};
            border: 2px solid {COLORS['red_light']};
        }}
        QPushButton:hover {{
            background-color: {COLORS['red_hover']};
        }}
    """

def button_move() -> str:
    """Style for move button (purple)"""
    return f"""
        QPushButton {{
            background-color: {COLORS['purple']};
            color: {COLORS['white']};
            border: 2px solid {COLORS['purple_light']};
            border-radius: 4px;
            padding: 8px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {COLORS['purple_hover']};
        }}
    """

def button_reconnect() -> str:
    """Style for reconnect buttons"""
    return button_action()  # Same as action buttons

def text_edit_dark() -> str:
    """Style for dark text edit fields"""
    return f"""
        QTextEdit {{
            background-color: {COLORS['gray_bg']};
            color: {COLORS['text_light']};
            border: 1px solid {COLORS['gray_dark']};
            border-radius: 3px;
            padding: 5px;
        }}
    """

def ping_table_widget_style() -> str:
    """Style for ping table widget"""
    return f"""
        QWidget {{
            border: 1px solid {COLORS['gray_dark']};
            border-radius: 4px;
            background-color: {COLORS['gray_bg_dark']};
        }}
    """

def spinbox_dark() -> str:
    """Style for dark spinbox"""
    return f"""
        QSpinBox {{
            background-color: {COLORS['gray_bg']};
            color: {COLORS['white']};
            border: 1px solid {COLORS['gray_dark']};
            border-radius: 3px;
            padding: 5px;
        }}
    """

