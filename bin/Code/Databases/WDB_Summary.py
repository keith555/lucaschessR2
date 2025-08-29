from PySide2 import QtWidgets, QtCore

import Code
from Code.Base import Game
from Code.Databases import WDB_Analysis
from Code.Openings import OpeningsStd
from Code.QT import Colocacion
from Code.QT import Columnas
from Code.QT import Controles
from Code.QT import Delegados
from Code.QT import FormLayout
from Code.QT import Grid
from Code.QT import Iconos
from Code.QT import QTUtil2
from Code.QT import QTVarios
from Code.Engines import EngineRun


class WSummary(QtWidgets.QWidget):
    def __init__(self, procesador, wb_database, db_games, siMoves=True):
        QtWidgets.QWidget.__init__(self)

        self.wb_database = wb_database

        self.db_games = db_games  # <--setdbGames
        self.infoMove = None  # <-- setInfoMove
        self.wmoves = None  # <-- setwmoves
        self.liMoves = []
        self.siMoves = siMoves
        self.procesador = procesador
        self.configuration = procesador.configuration
        self.foreground = Code.dic_qcolors["SUMMARY_FOREGROUND"]

        self.wdb_analysis = WDB_Analysis.WDBAnalisis(self)

        self.leeConfig()

        self.aperturasStd = OpeningsStd.ap

        self.with_figurines = self.configuration.x_pgn_withfigurines

        self.pvBase = ""

        self.orden = ["games", False]
        # Suppress the first auto-selection driven by external sync
        self._suppress_next_auto_goto = True

        self.lbName = (
            Controles.LB(self, "")
            .set_wrap()
            .align_center()
            .set_foreground_backgound("white", "#4E5A65")
            .set_font_type(puntos=10 if siMoves else 16)
        )
        self._lb_base_text = ""
        if not siMoves:
            self.lbName.hide()

        # Grid
        o_columns = Columnas.ListaColumnas()
        o_columns.nueva("number", _("N."), 35, align_center=True)
        self.delegadoMove = Delegados.EtiquetaPGN(True if self.with_figurines else None)
        o_columns.nueva("move", _("Move") + " *", 60, edicion=self.delegadoMove)
        o_columns.nueva("analysis", _("Analysis"), 60, align_right=True)
        o_columns.nueva("games", _("Games"), 70, align_right=True)
        o_columns.nueva("pgames", "% " + _("Games"), 70, align_right=True)
        o_columns.nueva("win", _("Win"), 70, align_right=True)
        o_columns.nueva("draw", _("Draw"), 70, align_right=True)
        o_columns.nueva("lost", _("Loss"), 70, align_right=True)
        o_columns.nueva("pwin", "% " + _("Win"), 60, align_right=True)
        o_columns.nueva("pdraw", "% " + _("Draw"), 60, align_right=True)
        o_columns.nueva("plost", "% " + _("Loss"), 60, align_right=True)
        o_columns.nueva("pdrawwin", "%% %s" % _("W+D"), 60, align_right=True)
        o_columns.nueva("pdrawlost", "%% %s" % _("L+D"), 60, align_right=True)

        self.grid = Grid.Grid(self, o_columns, xid="summary", siSelecFilas=True)
        self.grid.ponAltoFila(self.configuration.x_pgn_rowheight)
        self.grid.font_type(puntos=self.configuration.x_pgn_fontpoints)

        # ToolBar
        self.tb = QTVarios.LCTB(self, with_text=not self.siMoves)
        self.tb.new(_("Close"), Iconos.MainMenu(), wb_database.tw_terminar)
        self.tb.new(_("Basic position"), Iconos.Inicio(), self.start)
        self.tb.new(_("Previous"), Iconos.AnteriorF(), self.anterior, sep=False)
        self.tb.new(_("Next"), Iconos.SiguienteF(), self.siguiente)
        self.tb.new(_("Analyze"), Iconos.Analizar(), self.analizar)
        self.tb.new(_("Rebuild"), Iconos.Reindexar(), self.reindexar)
        self.tb.new(_("Config"), Iconos.Configurar(), self.config)
        if self.siMoves:
            self.tb.vertical()

        layout = Colocacion.V().control(self.lbName)
        if not self.siMoves:
            layout.control(self.tb)
        layout.control(self.grid)

        # Engine panel under the moves list (web-explorer style)
        self.engine_panel = EngineCandidatesPanel(self, self.procesador)
        layout.control(self.engine_panel)
        if self.siMoves:
            layout = Colocacion.H().control(self.tb).otro(layout)

        layout.margen(1)

        self.setLayout(layout)

    def close_db(self):
        if self.wdb_analysis:
            self.wdb_analysis.close()
            self.wdb_analysis = None
        if hasattr(self, "engine_panel") and self.engine_panel:
            self.engine_panel.finalize()

    def grid_doubleclick_header(self, grid, o_column):
        key = o_column.key

        if key == "analysis":

            def func(dic):
                return dic["analysis"].centipawns_abs() if dic["analysis"] else -9999999

        elif key == "move":

            def func(dic):
                return dic["move"].upper()

        else:

            def func(dic):
                return dic[key]

        tot = self.liMoves[-1]
        li = sorted(self.liMoves[:-1], key=func)

        orden, mas = self.orden
        if orden == key:
            mas = not mas
        else:
            mas = key == "move"
        if not mas:
            li.reverse()
        self.orden = key, mas
        li.append(tot)
        self.liMoves = li
        self.grid.refresh()

    def setdbGames(self, db_games):
        self.db_games = db_games

    def focusInEvent(self, event):
        self.wb_database.ultFocus = self

    def setInfoMove(self, infoMove):
        self.infoMove = infoMove

    def setwmoves(self, wmoves):
        self.wmoves = wmoves

    def grid_num_datos(self, grid):
        return len(self.liMoves)

    def grid_tecla_control(self, grid, k, is_shift, is_control, is_alt):
        if k in (QtCore.Qt.Key_Enter, QtCore.Qt.Key_Return, QtCore.Qt.Key_Right):
            self.siguiente()
        elif k == QtCore.Qt.Key_Left:
            self.anterior()
        else:
            return True  # que siga con el resto de teclas

    def grid_dato(self, grid, nfila, ocol):
        key = ocol.key

        # Last=Totals
        if self.siFilaTotales(nfila):
            if key in ("number", "analysis", "pgames"):
                return ""
            elif key == "move":
                return _("Total")

        if self.liMoves[nfila]["games"] == 0 and key not in ("number", "analysis", "move"):
            return ""
        v = self.liMoves[nfila][key]
        if key.startswith("p"):
            return "%.01f %%" % v
        elif key == "analysis":
            return v.abbrev_text_base() if v else ""
        elif key == "number":
            if self.with_figurines:
                self.delegadoMove.setWhite("..." not in v)
            return v
        else:
            return str(v)

    def posicionFila(self, nfila):
        dic = self.liMoves[nfila]
        li = [[k, dic[k]] for k in ("win", "draw", "lost")]
        li = sorted(li, key=lambda x: x[1], reverse=True)
        d = {}
        prev = 0
        ant = li[0][1]
        total = 0
        for cl, v in li:
            if v < ant:
                prev += 1
            d[cl] = prev
            ant = v
            total += v
        if total == 0:
            d["win"] = d["draw"] = d["lost"] = -1
        return d

    def grid_color_fondo(self, grid, nfila, ocol):
        key = ocol.key
        if self.siFilaTotales(nfila) and key not in ("number", "analysis"):
            return Code.dic_qcolors["SUMMARY_TOTAL"]
        if key in ("pwin", "pdraw", "plost"):
            dic = self.posicionFila(nfila)
            n = dic[key[1:]]
            if n == 0:
                return Code.dic_qcolors["SUMMARY_WIN"]
            if n == 2:
                return Code.dic_qcolors["SUMMARY_LOST"]

    def grid_color_texto(self, grid, nfila, ocol):
        if self.foreground:
            key = ocol.key
            if self.siFilaTotales(nfila) or key in ("pwin", "pdraw", "plost"):
                return self.foreground

    def popPV(self, pv):
        if pv:
            rb = pv.rfind(" ")
            if rb == -1:
                pv = ""
            else:
                pv = pv[:rb]
        return pv

    def analizar(self):
        self.wdb_analysis.menu(self.pvBase)
        self.actualizaPV(self.pvBase)

    def start(self):
        self.actualizaPV("")
        # Board is updated in actualizaPV to reflect pvBase

    def anterior(self):
        if self.pvBase:
            pv = self.popPV(self.pvBase)

            self.actualizaPV(pv)
            # Board is updated in actualizaPV to reflect pvBase

    def rehazActual(self):
        recno = self.grid.recno()
        if recno >= 0:
            dic = self.liMoves[recno]
            if "pv" in dic:
                pv = dic["pv"]
                if pv:
                    li = pv.split(" ")
                    pv = " ".join(li[:-1])
                self.actualizaPV(pv)
                self.cambiaInfoMove()

    def siguiente(self):
        recno = self.grid.recno()
        if recno >= 0:
            dic = self.liMoves[recno]
            if "pv" in dic:
                pv = dic["pv"]
                if pv.count(" ") > 0:
                    pv = "%s %s" % (self.pvBase, dic["pvmove"])
                self.actualizaPV(pv)
                # Board is updated in actualizaPV to reflect pvBase

    def reindexar(self):
        return self.reindexar_question(self.db_games.depth_stat(), True)

    def reindexar_question(self, depth, question):
        if not self.db_games.has_result_field():
            QTUtil2.message_error(self, _("This database does not have a RESULT field"))
            return

        if question or self.wb_database.is_temporary:
            # if not QTUtil2.pregunta(self, _("Do you want to rebuild stats?")):
            #     return

            li_gen = [(None, None)]
            li_gen.append((None, _("Select the number of half-moves <br> for each game to be considered")))
            li_gen.append((None, None))

            config = FormLayout.Spinbox(_("Depth"), 0, 999, 50)
            li_gen.append((config, self.db_games.depth_stat()))

            resultado = FormLayout.fedit(li_gen, title=_("Rebuild"), parent=self, icon=Iconos.Reindexar())
            if resultado is None:
                return None

            accion, li_resp = resultado

            depth = li_resp[0]

        self.RECCOUNT = 0

        bpTmp = QTUtil2.BarraProgreso1(self, _("Rebuilding"))
        bpTmp.mostrar()

        def dispatch(recno, reccount):
            if reccount != self.RECCOUNT:
                self.RECCOUNT = reccount
                bpTmp.set_total(reccount)
            bpTmp.pon(recno)
            return not bpTmp.is_canceled()

        self.db_games.rebuild_stat(dispatch, depth)
        bpTmp.cerrar()
        self.start()

    def movActivo(self):
        recno = self.grid.recno()
        if recno >= 0:
            return self.liMoves[recno]
        else:
            return None

    def siFilaTotales(self, nfila):
        return nfila == len(self.liMoves) - 1

    def noFilaTotales(self, nfila):
        return nfila < len(self.liMoves) - 1

    def grid_doble_click(self, grid, fil, col):
        if self.noFilaTotales(fil):
            self.siguiente()

    def gridActualiza(self):
        nfila = self.grid.recno()
        if nfila > -1:
            self.grid_cambiado_registro(None, nfila, None)

    def actualiza(self):
        movActual = self.infoMove.movActual
        pvBase = self.popPV(movActual.allPV())
        self.actualizaPV(pvBase)
        # On first open, do not auto-follow current move; wait for user input
        if self._suppress_next_auto_goto:
            self._suppress_next_auto_goto = False
            return
        if movActual:
            pv = movActual.allPV()
            for n in range(len(self.liMoves) - 1):
                if self.liMoves[n]["pv"] == pv:
                    self.grid.goto(n, 0)
                    return

    def actualizaPV(self, pvBase):
        self.pvBase = pvBase
        if not pvBase:
            pvMirar = ""
        else:
            pvMirar = self.pvBase

        dic_analisis = {}
        analisisMRM = self.wdb_analysis.mrm(pvMirar)
        if analisisMRM:
            for rm in analisisMRM.li_rm:
                dic_analisis[rm.movimiento()] = rm
        self.liMoves = self.db_games.get_summary(pvMirar, dic_analisis, self.with_figurines, self.allmoves)

        self.grid.refresh()
        # Do not auto-select the first move; leave no selection by default
        sm = self.grid.selectionModel()
        if sm is not None:
            sm.clearSelection()
            sm.setCurrentIndex(QtCore.QModelIndex(), QtCore.QItemSelectionModel.NoUpdate)
        self.grid.clearSelection()
        # Update board to reflect the current pvBase regardless of selection
        self.showBoardForPVBase()
        # Visual cue to confirm: append a tag when nothing is selected (only in siMoves mode)
        if self.siMoves and not pvMirar:
            if self._lb_base_text:
                self.lbName.set_text(f"{self._lb_base_text} [No move selected]")

    def showBoardForPVBase(self):
        if not self.infoMove:
            return
        p = Game.Game()
        if self.pvBase:
            p.read_pv(self.pvBase)
        p.is_finished()
        p.assign_opening()
        self.infoMove.game_mode(p, 9999)
        # Keep engine in sync with current pv/position
        if hasattr(self, "engine_panel") and self.engine_panel:
            self.engine_panel.set_game(p)

    def reset(self):
        self.actualizaPV(None)
        self.grid.refresh()
        # Leave grid without selection after reset
        sm = self.grid.selectionModel()
        if sm is not None:
            sm.clearSelection()
            sm.setCurrentIndex(QtCore.QModelIndex(), QtCore.QItemSelectionModel.NoUpdate)
        self.grid.clearSelection()

    def grid_cambiado_registro(self, grid, row, oCol):
        # Keep this lightweight: only update info pane on selection changes.
        # The actual move application happens on left-click via grid_left_button.
        if self.grid.hasFocus() or self.hasFocus():
            self.cambiaInfoMove()

    def grid_left_button(self, grid, row, column):
        # Single-click on a candidate applies it immediately.
        if row is not None and row >= 0 and self.noFilaTotales(row):
            self.siguiente()

    def cambiaInfoMove(self):
        sm = self.grid.selectionModel()
        if sm is None or not sm.hasSelection():
            return
        row = self.grid.recno()
        if row >= 0 and self.noFilaTotales(row):
            pv = self.liMoves[row]["pv"]
            p = Game.Game()
            p.read_pv(pv)
            p.is_finished()
            p.assign_opening()
            self.infoMove.game_mode(p, 9999)
            self.setFocus()
            self.grid.setFocus()
            # Restore base label when a move is selected
            if self.siMoves and self._lb_base_text:
                self.lbName.set_text(self._lb_base_text)

    def showActiveName(self, name):
        # Llamado de WBG_Games -> setNameToolbar
        base = _("Opening explorer of %s") % name
        self._lb_base_text = base
        # If no current selection and at root PV, keep the cue visible
        if self.siMoves and (not self.pvBase or not self.grid.currentIndex().isValid()):
            self.lbName.set_text(f"{base} [No move selected]")
        else:
            self.lbName.set_text(base)

    def leeConfig(self):
        dicConfig = self.configuration.read_variables("DBSUMMARY")
        if not dicConfig:
            dicConfig = {"allmoves": False}
        self.allmoves = dicConfig["allmoves"]
        return dicConfig

    def grabaConfig(self):
        dicConfig = {"allmoves": self.allmoves}
        self.configuration.write_variables("DBSUMMARY", dicConfig)
        self.configuration.graba()

    def config(self):
        menu = QTVarios.LCMenu(self)
        menu.opcion("allmoves", _("Show all moves"), is_checked=self.allmoves)
        resp = menu.lanza()
        if resp is None:
            return
        self.allmoves = not self.allmoves

        self.actualizaPV(self.pvBase)


class WSummaryBase(QtWidgets.QWidget):
    def __init__(self, procesador, db_stat):
        QtWidgets.QWidget.__init__(self)

        self.db_stat = db_stat
        self.liMoves = []
        self.procesador = procesador
        self.configuration = procesador.configuration
        self.foreground = Code.dic_qcolors["SUMMARY_FOREGROUND"]

        self.with_figurines = self.configuration.x_pgn_withfigurines

        self.orden = ["games", False]

        # Grid
        o_columns = Columnas.ListaColumnas()
        o_columns.nueva("number", _("N."), 35, align_center=True)
        self.delegadoMove = Delegados.EtiquetaPGN(True if self.with_figurines else None)
        o_columns.nueva("move", _("Move") + " *", 60, edicion=self.delegadoMove)
        o_columns.nueva("games", _("Games"), 70, align_right=True)
        o_columns.nueva("pgames", "% " + _("Games"), 70, align_right=True, align_center=True)
        o_columns.nueva("win", _("Win"), 70, align_right=True)
        o_columns.nueva("draw", _("Draw"), 70, align_right=True)
        o_columns.nueva("lost", _("Loss"), 70, align_right=True)
        o_columns.nueva("pwin", "% " + _("Win"), 60, align_right=True)
        o_columns.nueva("pdraw", "% " + _("Draw"), 60, align_right=True)
        o_columns.nueva("plost", "% " + _("Loss"), 60, align_right=True)
        o_columns.nueva("pdrawwin", "%% %s" % _("W+D"), 60, align_right=True)
        o_columns.nueva("pdrawlost", "%% %s" % _("L+D"), 60, align_right=True)

        self.grid = Grid.Grid(self, o_columns, xid="summarybase", siSelecFilas=True)

        layout = Colocacion.V()
        layout.control(self.grid)
        layout.margen(1)

        self.setLayout(layout)


class EngineCandidatesPanel(QtWidgets.QWidget):
    def __init__(self, owner, procesador):
        super().__init__()
        self.owner = owner
        self.procesador = procesador
        self.configuration = procesador.configuration
        self.with_figurines = self.configuration.x_pgn_withfigurines
        self.game = Game.Game()
        self.engine = None
        self.li_moves = []
        self.depth = 0
        self.running = False

        # Toolbar: start/stop toggle and depth label
        self.bt_toggle = QTVarios.LCTB(self, with_text=True)
        self.bt_toggle.new(_("Start engine"), Iconos.Kibitzer_Play(), self.start)
        self.bt_toggle.new(_("Stop engine"), Iconos.Kibitzer_Pause(), self.stop)
        self.bt_toggle.set_action_visible(self.stop, False)

        self.lbDepth = Controles.LB(self, "").anchoFijo(120)

        # Grid to show top-N moves
        o_columns = Columnas.ListaColumnas()
        delegado_best = Delegados.EtiquetaPGN(True if self.with_figurines else None)
        delegado_pgn = Delegados.LinePGN() if self.with_figurines else None
        o_columns.nueva("BESTMOVE", _("Best move"), 100, align_center=True, edicion=delegado_best)
        o_columns.nueva("EVALUATION", _("Evaluation"), 85, align_center=True)
        o_columns.nueva("MAINLINE", _("Main line"), 500, edicion=delegado_pgn)
        self.grid = Grid.Grid(self, o_columns, xid="db_engine_candidates", siSelecFilas=True)
        self.grid.ponAltoFila(self.configuration.x_pgn_rowheight)
        self.grid.font_type(puntos=self.configuration.x_pgn_fontpoints)
        # Use all available width
        try:
            self.grid.horizontalHeader().setStretchLastSection(True)
        except Exception:
            pass

        # Layout
        top = Colocacion.H().control(self.bt_toggle).relleno().control(self.lbDepth)
        layout = Colocacion.V().otro(top).control(self.grid).margen(2)
        self.setLayout(layout)

        # Timer for polling engine output
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.check_input)
        self.timer.setInterval(self.configuration.x_analyzer_mstime_refresh_ab or 200)
        self._last_sig = None

    def finalize(self):
        self.stop()
        self.timer.stop()

    # Grid API
    def grid_num_datos(self, grid):
        return len(self.li_moves)

    def grid_dato(self, grid, row, o_column):
        if not (0 <= row < len(self.li_moves)):
            return ""
        rm = self.li_moves[row]
        key = o_column.key
        if key == "EVALUATION":
            return rm.abbrev_text_base()
        elif key == "BESTMOVE":
            p = Game.Game(first_position=self.game.last_position)
            p.read_pv(rm.get_pv())
            if len(p) > 0:
                move = p.li_moves[0]
                resp = move.pgn_figurines() if self.with_figurines else move.pgn_translated()
                return resp
            return ""
        else:  # MAINLINE
            if rm.pv:
                p = Game.Game(first_position=self.game.last_position)
                p.read_pv(rm.pv)
                if p.li_moves:
                    move0 = p.li_moves[0]
                    p.first_position = move0.position
                    p.li_moves = p.li_moves[1:]
                    txt = p.pgn_base_raw() if self.with_figurines else p.pgn_translated()
                    return txt.lstrip("0123456789. ") if ".." in txt else txt

    def grid_doble_click(self, grid, row, o_column):
        if 0 <= row < len(self.li_moves):
            rm = self.li_moves[row]
            # Apply selected engine move to explorer: update pvBase through owner
            base_pv = self.game.pv()
            # When game represents only base_pv, append the move
            new_pv = (base_pv + " " + rm.movimiento()).strip()
            self.owner.actualizaPV(new_pv)
            # Keep engine and list in sync immediately
            g = Game.Game(first_position=self.game.first_position)
            g.read_pv(new_pv)
            self.set_game(g)
            try:
                self.owner.grid.refresh()
                self.owner.grid.gotop()
                sm = self.owner.grid.selectionModel()
                if sm is not None:
                    sm.clearSelection()
            except Exception:
                pass

    # Engine control
    def build_engine(self):
        conf_engine = self.configuration.engine_analyzer()
        # Choose a reasonable MultiPV
        multi = conf_engine.multiPV or min(conf_engine.maxMultiPV or 1, 10)
        if multi < 1:
            multi = 1
        return EngineRun.RunEngine(conf_engine.name, conf_engine.path_exe, conf_engine.liUCI, multi,
                                   priority=self.configuration.x_analyzer_priority, args=conf_engine.args)

    def start(self):
        if self.running:
            return
        try:
            self.engine = self.build_engine()
        except Exception:
            self.engine = None
        if not self.engine:
            return
        self.running = True
        self.bt_toggle.set_action_visible(self.start, False)
        self.bt_toggle.set_action_visible(self.stop, True)
        self.depth = 0
        self.li_moves = []
        self._last_sig = None
        self.grid.refresh()
        self.restart_engine_on_game()
        self.timer.start()

    def stop(self):
        if self.engine:
            try:
                self.engine.ac_final(0)
                self.engine.close()
            except Exception:
                pass
            self.engine = None
        self.running = False
        self.bt_toggle.set_action_visible(self.start, True)
        self.bt_toggle.set_action_visible(self.stop, False)
        self.timer.stop()
        self.lbDepth.set_text("")
        self._last_sig = None

    def set_game(self, game: Game.Game):
        # game is a copy for current pv/position
        if game is None:
            game = Game.Game()
        self.game = game
        if self.running:
            self.restart_engine_on_game()

    def restart_engine_on_game(self):
        if not self.engine:
            return
        try:
            # Ensure previous search is stopped promptly before starting a new one
            self.engine.put_line("stop")
            self.engine.ac_inicio(self.game)
        except Exception:
            pass

    def check_input(self):
        if not (self.engine and self.running):
            return
        mrm = self.engine.ac_estado()
        rm = mrm.rm_best()
        if rm is None:
            return
        best = rm.movimiento() or rm.get_pv()
        best = best.split(" ")[0] if best else ""
        sig = (rm.depth, len(mrm.li_rm), best)
        if sig != self._last_sig:
            self._last_sig = sig
            self.depth = rm.depth
            self.li_moves = mrm.li_rm
            self.lbDepth.set_text(f"Depth: {rm.depth}")
            self.grid.refresh()
