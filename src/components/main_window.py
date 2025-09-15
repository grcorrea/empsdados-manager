import flet as ft
from .theme_toggle import ThemeToggle
from .footer import Footer
from .tabs.sso_tab import SSOTab
from .tabs.s3_tab import S3Tab
from .tabs.eventbridge_tab import EventBridgeTab
from .tabs.stepfunctions_tab import StepFunctionsTab
from .tabs.glue_tab import GlueTab
from .tabs.athena_tab import AthenaTab
from .tabs.dashboard_tab import DashboardTab


class MainWindow(ft.Container):
    def __init__(self, page: ft.Page, settings):
        super().__init__()
        self.page = page
        self.settings = settings

        self.theme_toggle = ThemeToggle(page, settings)
        self.footer = Footer()

        # Criação das abas
        self.sso_tab = SSOTab(self.footer)
        self.s3_tab = S3Tab()
        self.eventbridge_tab = EventBridgeTab()
        self.stepfunctions_tab = StepFunctionsTab()
        self.glue_tab = GlueTab()
        self.athena_tab = AthenaTab()
        self.dashboard_tab = DashboardTab()

        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(
                    text="AWS SSO",
                    content=self.sso_tab
                ),
                ft.Tab(
                    text="S3 Files",
                    content=self.s3_tab
                ),
                ft.Tab(
                    text="EventBridge",
                    content=self.eventbridge_tab
                ),
                ft.Tab(
                    text="Step Functions",
                    content=self.stepfunctions_tab
                ),
                ft.Tab(
                    text="Glue",
                    content=self.glue_tab
                ),
                ft.Tab(
                    text="Athena",
                    content=self.athena_tab
                ),
                ft.Tab(
                    text="Dashboard",
                    content=self.dashboard_tab
                )
            ],
            expand=1
        )

        self.expand = True
        self.content = ft.Column(
            controls=[
                # Header
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Text(
                                "AWS SSO Manager",
                                size=18,
                                weight=ft.FontWeight.W_500,
                                color=ft.colors.ON_SURFACE
                            ),
                            self.theme_toggle
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    ),
                    padding=ft.padding.symmetric(horizontal=20, vertical=15),
                    border=ft.border.only(bottom=ft.border.BorderSide(1, ft.colors.OUTLINE))
                ),
                # Tabs Content
                self.tabs,
                # Footer
                self.footer
            ],
            expand=True,
            spacing=0
        )