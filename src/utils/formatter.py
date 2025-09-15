import json
from typing import Any, Dict
from datetime import datetime


class OutputFormatter:
    @staticmethod
    def format_json(data: Any, indent: int = 2) -> str:
        try:
            return json.dumps(data, indent=indent, ensure_ascii=False, default=str)
        except Exception as e:
            return f"Erro ao formatar JSON: {str(e)}"

    @staticmethod
    def format_table_data(data: list, headers: list = None) -> str:
        if not data:
            return "Nenhum dado encontrado"

        if not headers and isinstance(data[0], dict):
            headers = list(data[0].keys())

        if not headers:
            return str(data)

        max_widths = []
        for header in headers:
            max_width = len(str(header))
            for row in data:
                if isinstance(row, dict):
                    cell_value = str(row.get(header, ""))
                else:
                    cell_value = str(row)
                max_width = max(max_width, len(cell_value))
            max_widths.append(max_width)

        result = []

        header_row = " | ".join(
            str(header).ljust(max_widths[i]) for i, header in enumerate(headers)
        )
        result.append(header_row)
        result.append("-" * len(header_row))

        for row in data:
            if isinstance(row, dict):
                row_values = [str(row.get(header, "")).ljust(max_widths[i])
                             for i, header in enumerate(headers)]
            else:
                row_values = [str(row).ljust(max_widths[0])]

            result.append(" | ".join(row_values))

        return "\n".join(result)

    @staticmethod
    def format_aws_response(response: Dict[str, Any]) -> str:
        if not response.get("success", False):
            return f"❌ Erro: {response.get('error', 'Erro desconhecido')}"

        data = response.get("data", [])

        if not data:
            return "✅ Comando executado com sucesso, mas nenhum dado retornado"

        if isinstance(data, list):
            return f"✅ Sucesso!\n\n{OutputFormatter.format_table_data(data)}"
        elif isinstance(data, dict):
            return f"✅ Sucesso!\n\n{OutputFormatter.format_json(data)}"
        else:
            return f"✅ Sucesso!\n\n{str(data)}"

    @staticmethod
    def format_timestamp(timestamp: str) -> str:
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime("%d/%m/%Y %H:%M:%S")
        except:
            return timestamp