from __future__ import annotations

from PySide6.QtCharts import QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView, QValueAxis
from PySide6.QtCore import (
    Qt,
)
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from serial_vision.application_service import SerialVisionService
from serial_vision.contracts import StatisticsSummary
from serial_vision.ui.pages.base import Page
from serial_vision.ui.workers import StatisticsWorker


class StatisticsPage(Page):
    def __init__(
        self, service: SerialVisionService, locale: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(service, locale, parent)
        self.worker: StatisticsWorker | None = None
        self._generation = 0
        self._pending = False
        self._closing = False
        self.install(self.statistics())
        self.refresh_statistics()

    def statistics(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(
            self.help_button("statistics", "statistics"), alignment=Qt.AlignmentFlag.AlignRight
        )
        self.statistics_mode = QComboBox()
        self.statistics_mode.addItem(self.translate("day"), "day")
        self.statistics_mode.addItem(self.translate("month"), "month")
        self.statistics_mode.setCurrentIndex(1)
        self.statistics_mode.currentIndexChanged.connect(self.refresh_statistics)
        layout.addWidget(self.statistics_mode)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.statistics_table = self.table(
            [
                self.translate("date_time"),
                self.translate("receipt"),
                self.translate("issue"),
                self.translate("total"),
            ]
        )
        layout.addWidget(self.statistics_table)
        self.operations_chart = QChartView()
        self.services_chart = QChartView()
        self.models_chart = QChartView()
        for chart in (self.operations_chart, self.services_chart, self.models_chart):
            chart.setMinimumHeight(190)
            layout.addWidget(chart)
        return page

    def make_bar_chart(
        self, title: str, categories: list[str], series_values: list[tuple[str, list[int]]]
    ) -> QChart:
        series = QBarSeries()
        maximum = 1
        for label, values in series_values:
            bar_set = QBarSet(label)
            bar_set.append(values)
            series.append(bar_set)
            maximum = max([maximum, *values])
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(title)
        chart.legend().setVisible(len(series_values) > 1)
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_y = QValueAxis()
        axis_y.setRange(0, maximum)
        axis_y.setLabelFormat("%d")
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_x)
        series.attachAxis(axis_y)
        return chart

    def refresh_statistics(self) -> None:
        if self._closing:
            return
        self._generation += 1
        self._pending = True
        self.status.setText(self.translate("statistics_loading"))
        if self.worker is not None:
            self.worker.requestInterruption()
        else:
            self.start_worker()

    def start_worker(self) -> None:
        if self._closing or not self._pending:
            return
        self._pending = False
        generation = self._generation
        worker = StatisticsWorker(self.service, self.statistics_mode.currentData(), self)
        self.worker = worker
        worker.completed.connect(lambda result: self.statistics_loaded(result, generation))
        worker.failed.connect(lambda error: self.statistics_failed(error, generation))
        worker.finished.connect(lambda: self.worker_finished(worker))
        worker.start()

    def worker_finished(self, worker: StatisticsWorker) -> None:
        if self.worker is worker:
            self.worker = None
        worker.deleteLater()
        self.start_worker()

    def begin_shutdown(self) -> None:
        self._closing = True
        self._pending = False
        self._generation += 1

    def statistics_failed(self, error: str, generation: int) -> None:
        if not self._closing and generation == self._generation:
            self.status.setText(self.translate("statistics_failed", error=error))

    def statistics_loaded(self, summary: StatisticsSummary, generation: int) -> None:
        if self._closing or generation != self._generation:
            return
        self.status.clear()
        operations = summary["operations"]
        self.statistics_table.setRowCount(len(operations))
        categories = [self.period_label(period) for period in operations]
        receipt = [values["receipt"] for values in operations.values()]
        issue = [values["issue"] for values in operations.values()]
        for index, (period, values) in enumerate(operations.items()):
            self.fill(
                self.statistics_table,
                index,
                [
                    self.period_label(period),
                    values["receipt"],
                    values["issue"],
                    values["receipt"] + values["issue"],
                ],
            )
        self.operations_chart.setChart(
            self.make_bar_chart(
                self.translate("operation"),
                categories,
                [(self.translate("receipt"), receipt), (self.translate("issue"), issue)],
            )
        )
        services = summary["services"]
        self.services_chart.setChart(
            self.make_bar_chart(
                self.translate("service"),
                [self.translate(key) for key in services],
                [(self.translate("service"), list(services.values()))],
            )
        )
        models = dict(list(summary["models"].items())[:10])
        self.models_chart.setChart(
            self.make_bar_chart(
                self.translate("models"),
                list(models.keys()),
                [(self.translate("models"), list(models.values()))],
            )
        )
