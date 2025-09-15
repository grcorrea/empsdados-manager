import flet as ft
import os
from ...services.s3_service import S3Service


class S3Tab(ft.Container):
    def __init__(self):
        super().__init__()
        self.s3_service = S3Service()

        self.expand = True
        self.padding = 20

        # Dropdown para seleção de bucket
        self.bucket_dropdown = ft.Dropdown(
            label="Selecione um Bucket",
            width=300,
            options=[],
            on_change=self._on_bucket_selected
        )

        # Campo de prefixo/pasta
        self.prefix_field = ft.TextField(
            label="Prefixo/Pasta (opcional)",
            width=300,
            on_submit=self._list_objects
        )

        # Lista de objetos
        self.objects_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Nome", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Tamanho", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Modificado", size=12, weight=ft.FontWeight.W_500)),
                ft.DataColumn(ft.Text("Ações", size=12, weight=ft.FontWeight.W_500)),
            ],
            rows=[],
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=4
        )

        # Botões de ação
        self.refresh_buckets_btn = ft.Container(
            content=ft.Text("Atualizar Buckets", size=12),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=4,
            on_click=self._load_buckets,
            hover_color=ft.colors.SURFACE_VARIANT
        )

        self.list_objects_btn = ft.Container(
            content=ft.Text("Listar Objetos", size=12),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border=ft.border.all(1, ft.colors.PRIMARY),
            border_radius=4,
            bgcolor=ft.colors.PRIMARY_CONTAINER,
            on_click=self._list_objects
        )

        self.upload_btn = ft.Container(
            content=ft.Text("Upload Arquivo", size=12),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border=ft.border.all(1, ft.colors.SECONDARY),
            border_radius=4,
            bgcolor=ft.colors.SECONDARY_CONTAINER,
            on_click=self._upload_file
        )

        # FilePicker para upload
        self.file_picker = ft.FilePicker(
            on_result=self._on_file_selected
        )

        # Área de resultados
        self.result_text = ft.Container(
            content=ft.Text(
                "Selecione um bucket e liste os objetos...",
                size=12,
                color=ft.colors.ON_SURFACE_VARIANT,
                selectable=True
            ),
            padding=15,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=4,
            min_height=100
        )

        self.content = ft.Column(
            controls=[
                ft.Text("S3 File Management", size=16, weight=ft.FontWeight.W_500),
                ft.Container(height=10),

                # Controles de seleção
                ft.Row([
                    self.bucket_dropdown,
                    self.refresh_buckets_btn
                ], spacing=10),

                ft.Row([
                    self.prefix_field,
                    self.list_objects_btn,
                    self.upload_btn
                ], spacing=10),

                ft.Container(height=15),

                # Tabela de objetos
                ft.Text("Objetos no Bucket:", size=12, weight=ft.FontWeight.W_500),
                ft.Container(
                    content=self.objects_table,
                    height=300,
                    border=ft.border.all(1, ft.colors.OUTLINE),
                    border_radius=4
                ),

                ft.Container(height=15),

                # Resultados
                ft.Text("Resultados:", size=12, weight=ft.FontWeight.W_500),
                self.result_text,

                # Hidden file picker
                self.file_picker
            ],
            spacing=5,
            scroll=ft.ScrollMode.AUTO
        )

        # Carregar dados iniciais
        self._load_buckets(None)

    def _load_buckets(self, e):
        try:
            self._show_result("Carregando buckets...", is_error=False)

            result = self.s3_service.list_buckets()

            if result.get("success"):
                buckets = result.get("data", [])
                self.bucket_dropdown.options = [
                    ft.dropdown.Option(bucket['Name'], bucket['Name'])
                    for bucket in buckets
                ]

                if buckets:
                    self.bucket_dropdown.value = buckets[0]['Name']

                self._show_result(f"✓ {len(buckets)} buckets carregados", is_error=False)
            else:
                self._show_result(f"Erro ao carregar buckets: {result.get('error')}", is_error=True)

            self.update()

        except Exception as e:
            self._show_result(f"Erro inesperado: {str(e)}", is_error=True)

    def _on_bucket_selected(self, e):
        if self.bucket_dropdown.value:
            self._list_objects(None)

    def _list_objects(self, e):
        if not self.bucket_dropdown.value:
            self._show_result("Selecione um bucket primeiro", is_error=True)
            return

        try:
            bucket_name = self.bucket_dropdown.value
            prefix = self.prefix_field.value or ""

            self._show_result(f"Listando objetos em {bucket_name}...", is_error=False)

            result = self.s3_service.list_objects(bucket_name, prefix)

            if result.get("success"):
                data = result.get("data", {})
                objects = data.get("objects", [])
                folders = data.get("folders", [])

                # Limpar tabela
                self.objects_table.rows.clear()

                # Adicionar folders
                for folder in folders:
                    self.objects_table.rows.append(
                        ft.DataRow(
                            cells=[
                                ft.DataCell(ft.Text(f"📁 {folder['Key']}", size=11)),
                                ft.DataCell(ft.Text("-", size=11)),
                                ft.DataCell(ft.Text("-", size=11)),
                                ft.DataCell(ft.Text("-", size=11))
                            ]
                        )
                    )

                # Adicionar objetos
                for obj in objects:
                    download_btn = ft.IconButton(
                        icon=ft.icons.DOWNLOAD,
                        icon_size=16,
                        on_click=lambda e, key=obj['Key']: self._download_file(key)
                    )

                    delete_btn = ft.IconButton(
                        icon=ft.icons.DELETE,
                        icon_size=16,
                        icon_color=ft.colors.ERROR,
                        on_click=lambda e, key=obj['Key']: self._delete_file(key)
                    )

                    self.objects_table.rows.append(
                        ft.DataRow(
                            cells=[
                                ft.DataCell(ft.Text(obj['Key'], size=11)),
                                ft.DataCell(ft.Text(obj['Size'], size=11)),
                                ft.DataCell(ft.Text(obj['LastModified'], size=11)),
                                ft.DataCell(ft.Row([download_btn, delete_btn], spacing=5))
                            ]
                        )
                    )

                total_items = len(objects) + len(folders)
                self._show_result(f"✓ {total_items} itens encontrados em {bucket_name}", is_error=False)
            else:
                self._show_result(f"Erro ao listar objetos: {result.get('error')}", is_error=True)

            self.update()

        except Exception as e:
            self._show_result(f"Erro inesperado: {str(e)}", is_error=True)

    def _upload_file(self, e):
        if not self.bucket_dropdown.value:
            self._show_result("Selecione um bucket primeiro", is_error=True)
            return

        self.file_picker.pick_files(
            dialog_title="Selecione arquivo para upload",
            allow_multiple=False
        )

    def _on_file_selected(self, e: ft.FilePickerResultEvent):
        if not e.files:
            return

        try:
            file_path = e.files[0].path
            bucket_name = self.bucket_dropdown.value
            prefix = self.prefix_field.value or ""

            file_name = os.path.basename(file_path)
            object_key = f"{prefix}{file_name}" if prefix else file_name

            self._show_result(f"Enviando {file_name} para {bucket_name}...", is_error=False)

            result = self.s3_service.upload_file(file_path, bucket_name, object_key)

            if result.get("success"):
                self._show_result(result.get("message"), is_error=False)
                self._list_objects(None)  # Atualizar lista
            else:
                self._show_result(f"Erro no upload: {result.get('error')}", is_error=True)

        except Exception as e:
            self._show_result(f"Erro inesperado no upload: {str(e)}", is_error=True)

    def _download_file(self, object_key: str):
        if not self.bucket_dropdown.value:
            return

        try:
            bucket_name = self.bucket_dropdown.value

            # Pasta de download padrão
            downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
            file_name = os.path.basename(object_key)
            download_path = os.path.join(downloads_folder, file_name)

            self._show_result(f"Baixando {object_key}...", is_error=False)

            result = self.s3_service.download_file(bucket_name, object_key, download_path)

            if result.get("success"):
                self._show_result(result.get("message"), is_error=False)
            else:
                self._show_result(f"Erro no download: {result.get('error')}", is_error=True)

        except Exception as e:
            self._show_result(f"Erro inesperado no download: {str(e)}", is_error=True)

    def _delete_file(self, object_key: str):
        if not self.bucket_dropdown.value:
            return

        # Confirmar exclusão
        def confirm_delete(e):
            dialog.open = False
            self.page.update()

            try:
                bucket_name = self.bucket_dropdown.value
                self._show_result(f"Deletando {object_key}...", is_error=False)

                result = self.s3_service.delete_object(bucket_name, object_key)

                if result.get("success"):
                    self._show_result(result.get("message"), is_error=False)
                    self._list_objects(None)  # Atualizar lista
                else:
                    self._show_result(f"Erro na exclusão: {result.get('error')}", is_error=True)

            except Exception as e:
                self._show_result(f"Erro inesperado na exclusão: {str(e)}", is_error=True)

        def cancel_delete(e):
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar Exclusão"),
            content=ft.Text(f"Tem certeza que deseja deletar '{object_key}'?"),
            actions=[
                ft.TextButton("Cancelar", on_click=cancel_delete),
                ft.TextButton("Deletar", on_click=confirm_delete),
            ],
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _show_result(self, message: str, is_error: bool = False):
        color = ft.colors.ERROR if is_error else ft.colors.ON_SURFACE
        self.result_text.content = ft.Text(
            message,
            size=12,
            color=color,
            selectable=True
        )
        self.result_text.update()