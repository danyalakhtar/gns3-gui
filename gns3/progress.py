# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
from contextlib import contextmanager

from .qt import QtCore, QtWidgets, Qt, QtNetwork

log = logging.getLogger(__name__)


class Progress(QtCore.QObject):

    """
    Display a progress dialog when something is running
    """

    add_query_signal = QtCore.Signal(str, str, QtNetwork.QNetworkReply)
    remove_query_signal = QtCore.Signal(str)
    progress_signal = QtCore.Signal(str, int, int)

    def __init__(self, min_duration=1000):

        super().__init__()
        self._progress_dialog = None

        from .main_window import MainWindow
        self._parent = MainWindow.instance()

        self._stimer = QtCore.QTimer()
        self._finished_query_during_display = 0
        self._queries = {}
        # QtCore.Qt.QueuedConnection warranty that we execute the slot
        # in the current thread and not emitter thread.
        # This fix an issue with Qt 5.5
        self.add_query_signal.connect(self._addQuerySlot, QtCore.Qt.QueuedConnection)
        self.remove_query_signal.connect(self._removeQuerySlot, QtCore.Qt.QueuedConnection)
        self.progress_signal.connect(self._progressSlot, QtCore.Qt.QueuedConnection)

        self._minimum_duration = min_duration
        self._cancel_button_text = ""
        self._allow_cancel_query = False
        self._enable = True

    def _addQuerySlot(self, query_id, explanation, response):

        self._queries[query_id] = {"explanation": explanation, "current": 0, "maximum": 0, "response": response}
        self.show()

    def _removeQuerySlot(self, query_id):

        self._finished_query_during_display += 1
        if query_id in self._queries:
            del self._queries[query_id]

        if len(self._queries) == 0:
            self.hide()
        else:
            self.show()

    def progress_dialog(self):

        return self._progress_dialog

    def _progressSlot(self, query_id, current, maximum):
        if query_id in self._queries:
            self._queries[query_id]["current"] = current
            self._queries[query_id]["maximum"] = maximum
            self.show()

    def setAllowCancelQuery(self, allow_cancel_query):
        self._allow_cancel_query = allow_cancel_query

    def setCancelButtonText(self, text):
        self._cancel_button_text = text

    def _cancelSlot(self):
        log.debug("User ask for cancel running queries")
        if self._allow_cancel_query:
            log.debug("Cancel running queries")
            for query in self._queries.copy().values():
                query["response"].abort()

    def show(self):

        if self._progress_dialog is None or self._progress_dialog.wasCanceled():
            progress_dialog = QtWidgets.QProgressDialog("Waiting for server response", None, 0, 0, self._parent)
            progress_dialog.canceled.connect(self._cancelSlot)
            progress_dialog.setWindowModality(Qt.Qt.ApplicationModal)
            progress_dialog.setWindowTitle("Please wait")
            progress_dialog.setMinimumDuration(self._minimum_duration)

            if len(self._cancel_button_text) > 0:
                progress_dialog.setCancelButtonText(self._cancel_button_text)
            else:
                progress_dialog.setCancelButton(None)

            self._progress_dialog = progress_dialog
            self._finished_query_during_display = 0
            start_timer = True
        else:
            start_timer = False
            progress_dialog = self._progress_dialog

            # If we have multiple queries running progress show progress of the queries
            # otherwise it's the progress of the current query
            if len(self._queries) + self._finished_query_during_display > 1:
                progress_dialog.setMaximum(len(self._queries) + self._finished_query_during_display)
                progress_dialog.setValue(self._finished_query_during_display)
            elif len(self._queries) == 1:
                query = list(self._queries.values())[0]
                progress_dialog.setMaximum(query["maximum"])
                progress_dialog.setValue(query["current"])

        if len(self._queries) > 0:
            text = list(self._queries.values())[0]["explanation"]
            progress_dialog.setLabelText(text)

        if start_timer:
            self._stimer.singleShot(self._minimum_duration, self._show_dialog)

    def _show_dialog(self):
        if self._progress_dialog is not None and self._enable:
            self._progress_dialog.show()
            self._progress_dialog.exec_()

    def hide(self):
        """
        Hide and cancel the progress dialog
        """
        if self._progress_dialog is not None:
            progress_dialog = self._progress_dialog
            self._progress_dialog = None
            progress_dialog.cancel()
            progress_dialog.deleteLater()

    @contextmanager
    def context(self, **kwargs):
        """
        Change the behavior of the progress dialog when in this block
        and restore it at the end of the block.

        :param kwargs: Options to change (possible: min_duration, enable)
        """
        if 'min_duration' in kwargs:
            old_minimum_duration = self._minimum_duration
            self._minimum_duration = kwargs['min_duration']
        if 'enable' in kwargs:
            old_enable = self._enable
            self._enable = kwargs['enable']
        if 'cancel_button_text' in kwargs:
            old_cancel_button_text = self._cancel_button_text
            self._cancel_button_text = kwargs['cancel_button_text']
        if 'allow_cancel_query' in kwargs:
            old_allow_cancel_query = self._allow_cancel_query
            self._allow_cancel_query = kwargs['allow_cancel_query']
        yield
        if 'min_duration' in kwargs:
            self._minimum_duration = old_minimum_duration
        if 'enable' in kwargs:
            self._enable = old_enable
        if 'allow_cancel_query' in kwargs:
            self._allow_cancel_query = old_allow_cancel_query
        if 'cancel_button_text' in kwargs:
            self._cancel_button_text = old_cancel_button_text

    @staticmethod
    def instance():
        """
        Singleton to return only one instance of Progress.

        :returns: instance of Progress
        """

        if not hasattr(Progress, "_instance") or Progress._instance is None:
            Progress._instance = Progress()
        return Progress._instance
