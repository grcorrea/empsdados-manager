import flet as ft
import pyperclip
import pandas as pd
from datetime import datetime
from pathlib import Path
from utils.helpers import DateTimeHelper, DataHelper


class UIComponents:
    @staticmethod
    def safe_icon(icon_name, size=20, color=ft.Colors.WHITE, fallback_icon=ft.Icons.CIRCLE):
        """Cria ícone de forma segura com fallback"""
        try:
            return ft.Icon(icon_name, size=size, color=color)
        except Exception:
            return ft.Icon(fallback_icon, size=size, color=color)

    @staticmethod
    def create_status_container(text, color=ft.Colors.BLUE):
        """Cria container de status padronizado"""
        return ft.Container(
            content=ft.Text(text, color=color, size=14),
            padding=10,
            margin=ft.margin.only(bottom=10)
        )

    @staticmethod
    def create_filter_row(filter_text_field, refresh_button, additional_controls=None):
        """Cria linha de filtros padronizada"""
        controls = [
            ft.Container(
                content=filter_text_field,
                expand=True,
                margin=ft.margin.only(right=10)
            ),
            refresh_button
        ]

        if additional_controls:
            controls.extend(additional_controls)

        return ft.Row(
            controls=controls,
            alignment=ft.MainAxisAlignment.START,
            spacing=10
        )

    @staticmethod
    def create_action_button(text, icon, on_click, color=ft.Colors.BLUE):
        """Cria botão de ação padronizado"""
        return ft.ElevatedButton(
            text=text,
            icon=icon,
            on_click=on_click,
            bgcolor=color,
            color=ft.Colors.WHITE,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8)
            )
        )

    @staticmethod
    def create_data_table(columns, rows, on_sort_column=None):
        """Cria DataTable padronizada"""
        data_columns = []
        for col in columns:
            if isinstance(col, str):
                data_columns.append(ft.DataColumn(ft.Text(col, weight=ft.FontWeight.BOLD)))
            else:
                data_columns.append(col)

        return ft.DataTable(
            columns=data_columns,
            rows=rows,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
            vertical_lines=ft.BorderSide(1, ft.Colors.OUTLINE),
            horizontal_lines=ft.BorderSide(1, ft.Colors.OUTLINE),
            sort_column_index=None,
            sort_ascending=True,
            heading_row_color=ft.Colors.SURFACE_VARIANT,
            heading_text_style=ft.TextStyle(weight=ft.FontWeight.BOLD),
            data_row_min_height=50,
            data_row_max_height=100,
            column_spacing=20,
            show_checkbox_column=False
        )

    @staticmethod
    def create_kpi_container(number_text, label, color, bgcolor):
        """Cria container KPI padronizado"""
        return ft.Container(
            content=ft.Column([
                ft.Text(
                    number_text,
                    size=32,
                    weight=ft.FontWeight.BOLD,
                    color=color,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Text(
                    label,
                    size=14,
                    color=ft.Colors.ON_SURFACE,
                    text_align=ft.TextAlign.CENTER
                )
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=5),
            padding=20,
            bgcolor=bgcolor,
            border_radius=10,
            width=180,
            height=120,
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=3,
                color=ft.Colors.with_opacity(0.1, ft.Colors.BLACK),
                offset=ft.Offset(0, 2)
            )
        )

    @staticmethod
    def create_loading_indicator(text="Carregando..."):
        """Cria indicador de loading padronizado"""
        return ft.Column([
            ft.ProgressRing(width=50, height=50),
            ft.Text(text, size=16, text_align=ft.TextAlign.CENTER)
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=10)

    @staticmethod
    def create_error_container(error_message):
        """Cria container de erro padronizado"""
        return ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.ERROR, size=48, color=ft.Colors.RED),
                ft.Text(
                    "Erro ao carregar dados",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.RED,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Text(
                    str(error_message),
                    size=14,
                    color=ft.Colors.ON_SURFACE,
                    text_align=ft.TextAlign.CENTER
                )
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10),
            padding=40,
            alignment=ft.alignment.center
        )

    @staticmethod
    def copy_to_clipboard(data, data_type="dados"):
        """Copia dados para área de transferência"""
        try:
            if isinstance(data, list):
                if not data:
                    print(" Nenhum dado para copiar")
                    return False, "Nenhum dado para copiar"

                # Converter para DataFrame
                df = pd.DataFrame(data)

                # Converter para string formatada
                clipboard_text = df.to_string(index=False)

                # Copiar para clipboard
                pyperclip.copy(clipboard_text)

                message = f" {len(data)} {data_type} copiados para área de transferência"
                print(message)
                return True, message
            else:
                pyperclip.copy(str(data))
                message = f" {data_type} copiado para área de transferência"
                print(message)
                return True, message

        except Exception as e:
            error_msg = f" Erro ao copiar {data_type}: {e}"
            print(error_msg)
            return False, error_msg

    @staticmethod
    def export_to_excel(data, filename_prefix, export_folder, data_type="dados"):
        """Exporta dados para Excel"""
        try:
            if not data:
                return False, "Nenhum dado para exportar"

            # Criar DataFrame
            df = pd.DataFrame(data)

            # Gerar nome do arquivo com timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{filename_prefix}_{timestamp}.xlsx"
            filepath = Path(export_folder) / filename

            # Garantir que o diretório existe
            filepath.parent.mkdir(parents=True, exist_ok=True)

            # Salvar Excel
            df.to_excel(filepath, index=False, engine='openpyxl')

            message = f" {len(data)} {data_type} exportados para: {filepath.name}"
            print(message)
            return True, message

        except Exception as e:
            error_msg = f" Erro ao exportar {data_type}: {e}"
            print(error_msg)
            return False, error_msg

    @staticmethod
    def format_table_cell(value, cell_type="text"):
        """Formata células da tabela baseado no tipo"""
        if value is None or value == "N/A":
            return ft.Text("N/A", color=ft.Colors.OUTLINE)

        try:
            if cell_type == "datetime":
                return ft.Text(DateTimeHelper.format_timestamp(value))
            elif cell_type == "duration":
                return ft.Text(DateTimeHelper.format_duration(value))
            elif cell_type == "size":
                return ft.Text(DataHelper.format_file_size(value))
            elif cell_type == "status":
                return ft.Text(str(value), weight=ft.FontWeight.BOLD)
            elif cell_type == "number":
                return ft.Text(f"{value:,}" if isinstance(value, (int, float)) else str(value))
            else:
                return ft.Text(str(value))
        except:
            return ft.Text(str(value))

    @staticmethod
    def create_sidebar_item(icon, text, on_click, is_selected=False):
        """Cria item da sidebar padronizado"""
        return ft.Container(
            content=ft.Row([
                UIComponents.safe_icon(icon, size=20, color=ft.Colors.WHITE),
                ft.Text(text, color=ft.Colors.WHITE, size=14)
            ], spacing=10),
            padding=ft.padding.symmetric(horizontal=15, vertical=10),
            bgcolor=ft.Colors.BLUE_600 if is_selected else None,
            border_radius=8,
            margin=ft.margin.only(bottom=5),
            on_click=on_click,
            ink=True
        )

    @staticmethod
    def create_expandable_menu(title, icon, items, expanded=False, on_toggle=None):
        """Cria menu expansível da sidebar"""
        return ft.ExpansionTile(
            title=ft.Row([
                UIComponents.safe_icon(icon, size=20, color=ft.Colors.WHITE),
                ft.Text(title, color=ft.Colors.WHITE, size=14)
            ], spacing=10),
            subtitle=ft.Text("", size=1),  # Placeholder para manter altura
            controls=items,
            initially_expanded=expanded,
            on_change=on_toggle,
            bgcolor=ft.Colors.BLUE_700,
            collapsed_bgcolor=ft.Colors.BLUE_800,
            text_color=ft.Colors.WHITE,
            icon_color=ft.Colors.WHITE,
            maintain_state=True
        )

    @staticmethod
    def create_tab_header(title, icon, subtitle=None):
        """Cria cabeçalho padronizado para tabs"""
        controls = [
            ft.Row([
                UIComponents.safe_icon(icon, size=24, color=ft.Colors.BLUE),
                ft.Text(title, size=20, weight=ft.FontWeight.BOLD)
            ], spacing=10)
        ]

        if subtitle:
            controls.append(
                ft.Text(subtitle, size=14, color=ft.Colors.OUTLINE)
            )

        return ft.Column(
            controls=controls,
            spacing=5,
            alignment=ft.MainAxisAlignment.START
        )

    @staticmethod
    def create_form_field(label, control, required=False, help_text=None):
        """Cria campo de formulário padronizado"""
        label_text = f"{label}{'*' if required else ''}"

        controls = [
            ft.Text(label_text, size=14, weight=ft.FontWeight.BOLD),
            control
        ]

        if help_text:
            controls.append(
                ft.Text(help_text, size=12, color=ft.Colors.OUTLINE)
            )

        return ft.Column(
            controls=controls,
            spacing=5,
            alignment=ft.MainAxisAlignment.START
        )