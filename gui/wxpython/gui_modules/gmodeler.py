"""!
@package gmodeler.py

@brief Graphical modeler to create edit, and manage models

Classes:
 - Model
 - ModelFrame
 - ModelCanvas
 - ModelAction
 - ModelSearchDialog
 - ModelData
 - ModelDataDialog
 - ModelRelation
 - ProcessModelFile
 - WriteModelFile
 - PreferencesDialog
 - PropertiesDialog
 - ModelParamDialog

(C) 2010 by the GRASS Development Team
This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author Martin Landa <landa.martin gmail.com>
"""

import os
import sys
import shlex
import time
import traceback
import getpass
import stat
import textwrap
import tempfile
import copy

try:
    import xml.etree.ElementTree as etree
except ImportError:
    import elementtree.ElementTree as etree # Python <= 2.4

import globalvar
if not os.getenv("GRASS_WXBUNDLED"):
    globalvar.CheckForWx()
import wx
import wx.lib.ogl as ogl
import wx.lib.flatnotebook as FN
import wx.lib.colourselect as csel

import menu
import menudata
import toolbars
import menuform
import prompt
import utils
import goutput
import gselect
from debug        import Debug
from gcmd         import GMessage, GError
from gdialogs     import ElementDialog, GetImageHandlers
from preferences  import PreferencesBaseDialog, globalSettings as UserSettings
from ghelp        import SearchModuleWindow

from grass.script import core as grass

class Model(object):
    """!Class representing the model"""
    def __init__(self, canvas = None):
        self.actions = list()    # list of recorded actions
        self.data    = list()    # list of recorded data items
        
        self.canvas  = canvas
        
    def GetCanvas(self):
        """!Get canvas or None"""
        return self.canvas
    
    def GetActions(self):
        """!Return list of actions"""
        return self.actions

    def GetData(self):
        """!Return list of data"""
        return self.data

    def Reset(self):
        """!Reset model"""
        self.actions = list()
        self.data    = list()
        
    def AddAction(self, item):
        """!Add action to the model"""
        self.actions.append(item)
        
    def AddData(self, item):
        """!Add data to the model"""
        self.data.append(item)
        
    def RemoveItem(self, item):
        """!Remove item from model"""
        if isinstance(item, ModelAction):
            self.actions.remove(item)
        elif isinstance(item, ModelData):
            self.data.remove(item)
        
    def FindAction(self, id):
        """!Find action by id"""
        for action in self.actions:
            if action.GetId() == id:
                return action
        
        return None

    def FindData(self, value, prompt):
        """!Find data by value, and prompt"""
        for data in self.data:
            if data.GetValue() == value and \
                    data.GetPrompt() == prompt:
                return data
        
        return None
    
    def LoadModel(self, filename):
        """!Load model definition stored in GRASS Model XML file (gxm)
        
        @todo Validate against DTD
        
        Raise exception on error.
        """
        dtdFilename = os.path.join(globalvar.ETCWXDIR, "xml", "grass-gxm.dtd")
        
        # parse workspace file
        try:
            gxmXml = ProcessModelFile(etree.parse(filename))
        except StandardError, e:
            raise GError(e)
        
        # load model.GetActions()
        for action in gxmXml.actions:
            actionItem = ModelAction(parent = self, 
                                     x = action['pos'][0],
                                     y = action['pos'][1],
                                     width = action['size'][0],
                                     height = action['size'][1],
                                     task = action['task'])
            actionItem.SetId(action['id'])

            self.actions.append(actionItem)
            
            task = menuform.GUI().ParseCommand(cmd = actionItem.GetLog(string = False),
                                               show = None)
            valid = True
            for p in task.get_options()['params']:
                if p.get('value', '') == '' and \
                        p.get('default', '') == '':
                    valid = False
                    break
            actionItem.SetValid(valid)
        
        # load data & connections
        for data in gxmXml.data:
            dataItem = ModelData(parent = self, 
                                 x = data['pos'][0],
                                 y = data['pos'][1],
                                 width = data['size'][0],
                                 height = data['size'][1],
                                 name = data['name'],
                                 prompt = data['prompt'],
                                 value = data['value'])
            dataItem.SetIntermediate(data['intermediate'])
            
            for rel in data['rels']:
                actionItem = self.FindAction(rel['id'])
                if rel['dir'] == 'from':
                    relation = ModelRelation(dataItem, actionItem)
                    relation.SetControlPoints(rel['points'])
                    dataItem.AddRelation(relation, direction = 'from')
                else:
                    relation = ModelRelation(actionItem, dataItem)
                    relation.SetControlPoints(rel['points'])
                    dataItem.AddRelation(relation, direction = 'to')
            
            self.data.append(dataItem)
            
            actionItem.AddData(dataItem)
        
    def IsValid(self):
        """Return True if model is valid"""
        if self.Validate():
            return False
        
        return True
    
    def Validate(self):
        """!Validate model, return None if model is valid otherwise
        error string"""
        errList = list()
        for action in self.actions:
            task = menuform.GUI().ParseCommand(cmd = action.GetLog(string = False),
                                               show = None)
            errList += task.getCmdError()

        return errList

    def Run(self, log, onDone):
        """!Run model"""
        for action in self.actions:
            log.RunCmd(command = action.GetLog(string = False),
                       onDone = onDone)
    
    def DeleteIntermediateData(self, log):
        """!Detele intermediate data"""
        rast, vect, rast3d, msg = self.GetIntermediateData()
        
        if rast:
            log.RunCmd(['g.remove', 'rast=%s' %','.join(rast)])
        if rast3d:
            log.RunCmd(['g.remove', 'rast3d=%s' %','.join(rast3d)])
        if vect:
            log.RunCmd(['g.remove', 'vect=%s' %','.join(vect)])
        
    def GetIntermediateData(self):
        """!Get info about intermediate data"""
        rast = list()
        rast3d = list()
        vect = list()
        for data in self.data:
            if not data.IsIntermediate():
                continue
            name = data.GetValue()
            prompt = data.GetPrompt()
            if prompt == 'raster':
                rast.append(name)
            elif prompt == 'vector':
                vect.append(name)
            elif prompt == 'rast3d':
                rast3d.append(name)
        
        msg = ''
        if rast:
            msg += '\n\n%s: ' % _('Raster maps')
            msg += ', '.join(rast)
        if rast3d:
            msg += '\n\n%s: ' % _('3D raster maps')
            msg += ', '.join(rast3d)
        if vect:
            msg += '\n\n%s: ' % _('Vector maps')
            msg += ', '.join(vect)
        
        return rast, vect, rast3d, msg

    def Update(self):
        """!Update model"""
        for action in self.actions:
            action.Update()
        
        for data in self.data:
            data.Update()

    def IsParameterized(self):
        """!Return True if model is parameterized"""
        if self.Parametrize():
            return True
        
        return False
    
    def Parametrize(self):
        """!Return parameterized options"""
        result = dict()
        idx = 0
        for action in self.actions:
            name   = action.GetName()
            params = action.GetParams()
            for f in params['flags']:
                if f.get('parameterized', False):
                    if not result.has_key(name):
                        result[name] = { 'flags' : list(),
                                         'params': list(),
                                         'idx'   : idx }
                    result[name]['flags'].append(f)
            for p in params['params']:
                if p.get('parameterized', False):
                    if not result.has_key(name):
                        result[name] = { 'flags' : list(),
                                         'params': list(),
                                         'idx'   : idx }
                    result[name]['params'].append(p)
            idx += 1
        
        return result
    
class ModelFrame(wx.Frame):
    def __init__(self, parent, id = wx.ID_ANY,
                 title = _("GRASS GIS Graphical Modeler"), **kwargs):
        """!Graphical modeler main window
        
        @param parent parent window
        @param id window id
        @param title window title

        @param kwargs wx.Frames' arguments
        """
        self.parent = parent
        self.searchDialog = None # module search dialog
        self.baseTitle = title
        self.modelFile = None    # loaded model
        self.modelChanged = False
        self.properties = None
        
        self.cursors = {
            "default" : wx.StockCursor(wx.CURSOR_ARROW),
            "cross"   : wx.StockCursor(wx.CURSOR_CROSS),
            }
        
        wx.Frame.__init__(self, parent = parent, id = id, title = title, **kwargs)
        self.SetName("Modeler")
        self.SetIcon(wx.Icon(os.path.join(globalvar.ETCICONDIR, 'grass.ico'), wx.BITMAP_TYPE_ICO))
        
        self.menubar = menu.Menu(parent = self, data = menudata.ModelerData())
        
        self.SetMenuBar(self.menubar)
        
        self.toolbar = toolbars.ModelToolbar(parent = self)
        self.SetToolBar(self.toolbar)
        
        self.statusbar = self.CreateStatusBar(number = 1)
        
        self.notebook = FN.FlatNotebook(parent = self, id = wx.ID_ANY,
                                        style = FN.FNB_FANCY_TABS | FN.FNB_BOTTOM |
                                        FN.FNB_NO_NAV_BUTTONS | FN.FNB_NO_X_BUTTON)
        
        self.canvas = ModelCanvas(self)
        self.canvas.SetBackgroundColour(wx.WHITE)
        self.canvas.SetCursor(self.cursors["default"])
        
        self.model = Model(self.canvas)
        
        self.goutput = goutput.GMConsole(parent = self, pageid = 1,
                                         notebook = self.notebook)
        
        self.modelPage   = self.notebook.AddPage(self.canvas, text=_('Model'))
        self.commandPage = self.notebook.AddPage(self.goutput, text=_('Command output'))
        wx.CallAfter(self.notebook.SetSelection, 0)
        
        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        
        self._layout()
        self.SetMinSize((350, 200))
        self.SetSize((640, 480))
        
        # fix goutput's pane size
        if self.goutput:
            self.goutput.SetSashPosition(int(self.GetSize()[1] * .75))
        
    def _layout(self):
        """!Do layout"""
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(item = self.notebook, proportion = 1,
                  flag = wx.EXPAND)
        
        self.SetAutoLayout(True)
        self.SetSizer(sizer)
        sizer.Fit(self)
        
        self.Layout()

    def _addEvent(self, item):
        """!Add event to item"""
        evthandler = ModelEvtHandler(self.statusbar,
                                     self)
        evthandler.SetShape(item)
        evthandler.SetPreviousHandler(item.GetEventHandler())
        item.SetEventHandler(evthandler)

    def GetCanvas(self):
        """!Get canvas"""
        return self.canvas
    
    def GetModel(self):
        """!Get model"""
        return self.model
    
    def ModelChanged(self):
        """!Update window title"""
        if not self.modelChanged:
            self.modelChanged = True
        
        if self.modelFile:
            self.SetTitle(self.baseTitle + " - " +  os.path.basename(self.modelFile) + '*')

    def OnRemoveItem(self, event):
        """!Remove shape
        """
        self.GetCanvas().RemoveSelected()
        
    def OnCloseWindow(self, event):
        """!Close window"""
        self.Destroy()

    def OnPreferences(self, event):
        """!Open preferences dialog"""
        dlg = PreferencesDialog(parent = self)
        dlg.CenterOnParent()
        
        dlg.ShowModal()
        self.canvas.Refresh()
        
    def OnModelProperties(self, event):
        """!Model properties dialog"""
        dlg = PropertiesDialog(parent = self)
        dlg.CentreOnParent()
        if self.properties:
            dlg.Init(self.properties)
        else:
            dlg.Init({ 'name' : '',
                       'desc' : '',
                       'author' : getpass.getuser() })
        if dlg.ShowModal() == wx.ID_OK:
            self.properties = dlg.GetValues()
            for action in self.model.GetActions():
                action.GetTask().set_flag('overwrite', self.properties['overwrite'])
        
        dlg.Destroy()
        
    def OnDeleteData(self, event):
        """!Delete intermediate data"""
        rast, vect, rast3d, msg = self.model.GetIntermediateData()
        
        if not rast and not vect and not rast3d:
            GMessage(parent = self,
                     message = _('Nothing to delete.'),
                     msgType = 'info')
            return
        
        dlg = wx.MessageDialog(parent = self,
                               message= _("Do you want to permanently delete data?%s" % msg),
                               caption=_("Delete intermediate data?"),
                               style=wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
        
        ret = dlg.ShowModal()
        if ret == wx.ID_YES:
            dlg.Destroy()
            
            if rast:
                self.goutput.RunCmd(['g.remove', 'rast=%s' %','.join(rast)])
            if rast3d:
                self.goutput.RunCmd(['g.remove', 'rast3d=%s' %','.join(rast3d)])
            if vect:
                self.goutput.RunCmd(['g.remove', 'vect=%s' %','.join(vect)])
            
            self.SetStatusText(_("%d maps deleted from current mapset") % \
                                 int(len(rast) + len(rast3d) + len(vect)))
            return
        
        dlg.Destroy()
                
    def OnModelNew(self, event):
        """!Create new model"""
        Debug.msg(4, "ModelFrame.OnModelNew():")
        
        # ask user to save current model
        if self.modelFile and self.modelChanged:
            self.OnModelSave()
        elif self.modelFile is None and \
                (len(self.model.GetActions()) > 0 or len(self.model.GetData()) > 0):
            dlg = wx.MessageDialog(self, message=_("Current model is not empty. "
                                                   "Do you want to store current settings "
                                                   "to model file?"),
                                   caption=_("Create new model?"),
                                   style=wx.YES_NO | wx.YES_DEFAULT |
                                   wx.CANCEL | wx.ICON_QUESTION)
            ret = dlg.ShowModal()
            if ret == wx.ID_YES:
                self.OnModelSaveAs()
            elif ret == wx.ID_CANCEL:
                dlg.Destroy()
                return
            
            dlg.Destroy()
        
        # delete all items
        self.canvas.GetDiagram().DeleteAllShapes()
        self.model.Reset()
        self.canvas.Refresh()
        
        # no model file loaded
        self.modelFile = None
        self.modelChanged = False
        self.SetTitle(self.baseTitle)
        
    def OnModelOpen(self, event):
        """!Load model from file"""
        filename = ''
        dlg = wx.FileDialog(parent = self, message=_("Choose model file"),
                            defaultDir = os.getcwd(),
                            wildcard=_("GRASS Model File (*.gxm)|*.gxm"))
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetPath()
                    
        if not filename:
            return
        
        Debug.msg(4, "ModelFrame.OnModelOpen(): filename=%s" % filename)
        
        # close current model
        self.OnModelClose()
        
        self.LoadModelFile(filename)
        
        self.modelFile = filename
        self.SetTitle(self.baseTitle + " - " +  os.path.basename(self.modelFile))
        self.SetStatusText(_('%d actions loaded into model') % len(self.model.GetActions()), 0)
        
    def OnModelSave(self, event = None):
        """!Save model to file"""
        if self.modelFile and self.modelChanged:
            dlg = wx.MessageDialog(self, message=_("Model file <%s> already exists. "
                                                   "Do you want to overwrite this file?") % \
                                       self.modelFile,
                                   caption=_("Save model"),
                                   style=wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
            if dlg.ShowModal() == wx.ID_NO:
                dlg.Destroy()
            else:
                Debug.msg(4, "ModelFrame.OnModelSave(): filename=%s" % self.modelFile)
                self.WriteModelFile(self.modelFile)
                self.SetStatusText(_('File <%s> saved') % self.modelFile, 0)
                self.SetTitle(self.baseTitle + " - " +  os.path.basename(self.modelFile))
        elif not self.modelFile:
            self.OnModelSaveAs(None)
        
    def OnModelSaveAs(self, event):
        """!Create model to file as"""
        filename = ''
        dlg = wx.FileDialog(parent = self,
                            message = _("Choose file to save current model"),
                            defaultDir = os.getcwd(),
                            wildcard=_("GRASS Model File (*.gxm)|*.gxm"),
                            style=wx.FD_SAVE)
        
        
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetPath()
        
        if not filename:
            return
        
        # check for extension
        if filename[-4:] != ".gxm":
            filename += ".gxm"
        
        if os.path.exists(filename):
            dlg = wx.MessageDialog(parent = self,
                                   message=_("Model file <%s> already exists. "
                                             "Do you want to overwrite this file?") % filename,
                                   caption=_("File already exists"),
                                   style=wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
            if dlg.ShowModal() != wx.ID_YES:
                dlg.Destroy()
                return
        
        Debug.msg(4, "GMFrame.OnModelSaveAs(): filename=%s" % filename)
        
        self.WriteModelFile(filename)
        self.modelFile = filename
        self.SetTitle(self.baseTitle + " - " + os.path.basename(self.modelFile))
        self.SetStatusText(_('File <%s> saved') % self.modelFile, 0)

    def OnModelClose(self, event = None):
        """!Close model file"""
        Debug.msg(4, "ModelFrame.OnModelClose(): file=%s" % self.modelFile)
        # ask user to save current model
        if self.modelFile and self.modelChanged:
            self.OnModelSave()
        elif self.modelFile is None and \
                (len(self.model.GetActions()) > 0 or len(self.model.GetData()) > 0):
            dlg = wx.MessageDialog(self, message=_("Current model is not empty. "
                                                   "Do you want to store current settings "
                                                   "to model file?"),
                                   caption=_("Create new model?"),
                                   style=wx.YES_NO | wx.YES_DEFAULT |
                                   wx.CANCEL | wx.ICON_QUESTION)
            ret = dlg.ShowModal()
            if ret == wx.ID_YES:
                self.OnModelSaveAs()
            elif ret == wx.ID_CANCEL:
                dlg.Destroy()
                return
            
            dlg.Destroy()
        
        self.modelFile = None
        self.SetTitle(self.baseTitle)
        
        self.canvas.GetDiagram().DeleteAllShapes()
        self.model.Reset()
        
        self.canvas.Refresh()
        
    def OnRunModel(self, event):
        """!Run entire model"""
        if len(self.model.GetActions()) < 1:
            GMessage(parent = self, 
                     message = _('Model is empty. Nothing to run.'),
                     msgType = 'info')
            return
        
        # validation
        errList = self._validateModel()
        if errList:
            dlg = wx.MessageDialog(parent = self,
                                   message = _('Model is not valid. Do you want to '
                                               'run the model anyway?\n\n%s') % '\n'.join(errList),
                                   caption=_("Run model?"),
                                   style = wx.YES_NO | wx.NO_DEFAULT |
                                   wx.ICON_QUESTION | wx.CENTRE)
            ret = dlg.ShowModal()
            if ret != wx.ID_YES:
                return
        
        # parametrization
        params = self.model.Parametrize()
        if params:
            dlg = ModelParamDialog(parent = self,
                                   params = params)
            dlg.CenterOnParent()
            
            ret = dlg.ShowModal()
            if ret != wx.ID_OK:
                dlg.Destroy()
                return
        
        self.goutput.cmdThread.SetId(-1)
        for action in self.model.GetActions():
            name = action.GetName()
            if params.has_key(name):
                paramsOrig = action.GetParams(dcopy = True)
                action.MergeParams(params[name])
            
            self.SetStatusText(_('Running model...'), 0) 
            self.goutput.RunCmd(command = action.GetLog(string = False),
                                onDone = self.OnDone)
            
            if params.has_key(name):
                action.SetParams(paramsOrig)
        
        if params:
            dlg.Destroy()
        
    def OnDone(self, returncode):
        """!Computation finished"""
        self.SetStatusText('', 0)
        
    def OnValidateModel(self, event, showMsg = True):
        """!Validate entire model"""
        if len(self.model.GetActions()) < 1:
            GMessage(parent = self, 
                     message = _('Model is empty. Nothing to validate.'),
                     msgType = 'info')
            return
        
        errList = self._validateModel()
        
        if errList:
            GMessage(parent = self,
                     message = _('Model is not valid.\n\n%s') % '\n'.join(errList),
                     msgType = 'warning')
        else:
            GMessage(parent = self,
                     message = _('Model is valid.'),
                     msgType = 'info')
    
    def OnExportImage(self, event):
        """!Export model to image (default image)
        """
        xminImg = 0
        xmaxImg = 0
        yminImg = 0
        ymaxImg = 0
        for shape in self.canvas.GetDiagram().GetShapeList():
            w, h = shape.GetBoundingBoxMax()
            x    = shape.GetX()
            y    = shape.GetY()
            xmin = x - w / 2
            xmax = x + w / 2
            ymin = y - h / 2
            ymax = y + h / 2
            if xmin < xminImg:
                xminImg = xmin
            if xmax > xmaxImg:
                xmaxImg = xmax
            if ymin < yminImg:
                xminImg = xmin
            if ymax < ymaxImg:
                xminImg = xmin
            
        size = wx.Size(int(xmaxImg - xminImg),
                       int(ymaxImg - ymaxImg))
        bitmap = wx.EmptyBitmap(width = size.width, height = size.height)
        
        filetype, ltype = GetImageHandlers(wx.ImageFromBitmap(bitmap))
        
        dlg = wx.FileDialog(parent = self,
                            message = _("Choose a file name to save the image (no need to add extension)"),
                            defaultDir = "",
                            defaultFile = "",
                            wildcard = filetype,
                            style=wx.SAVE | wx.FD_OVERWRITE_PROMPT)
        
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            if not path:
                dlg.Destroy()
                return
            
            base, ext = os.path.splitext(path)
            fileType = ltype[dlg.GetFilterIndex()]['type']
            extType  = ltype[dlg.GetFilterIndex()]['ext']
            if ext != extType:
                path = base + '.' + extType
                
            dc = wx.MemoryDC(bitmap)
            dc.SetBackground(wx.WHITE_BRUSH)
            dc.SetBackgroundMode(wx.SOLID)
            
            dc.BeginDrawing()
            self.canvas.GetDiagram().Clear(dc)
            self.canvas.GetDiagram().Redraw(dc)
            dc.EndDrawing()
            
            bitmap.SaveFile(path, fileType)
            self.SetStatusText(_("Model exported to <%s>") % path)
            
        dlg.Destroy()
        
    def OnExportPython(self, event):
        """!Export model to Python script"""
        filename = ''
        dlg = wx.FileDialog(parent = self,
                            message = _("Choose file to save"),
                            defaultDir = os.getcwd(),
                            wildcard=_("Python script (*.py)|*.py"),
                            style=wx.FD_SAVE)
        
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetPath()
        
        if not filename:
            return

        # check for extension
        if filename[-3:] != ".py":
            filename += ".py"
        
        if os.path.exists(filename):
            dlg = wx.MessageDialog(self, message=_("File <%s> already exists. "
                                                   "Do you want to overwrite this file?") % filename,
                                   caption=_("Save file"),
                                   style=wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
            if dlg.ShowModal() == wx.ID_NO:
                dlg.Destroy()
                return
            
            dlg.Destroy()

        fd = open(filename, "w")
        try:
            self._writePython(fd)
        finally:
            fd.close()
        
        # executable file
        os.chmod(filename, stat.S_IRWXU | stat.S_IWUSR)
        
        self.SetStatusText(_("Model exported to <%s>") % filename)

    def _writePython(self, fd):
        """!Write model to file"""
        if self.properties:
            properties = self.properties
        else:
            properties = { 'name' : _("Graphical modeler script"),
                           'desc' : _("Script generated by wxGUI Graphical Modeler"),
                           'author' : getpass.getuser() }
        
        fd.write(
r"""#!/usr/bin/env python
#
############################################################################
#
# MODULE:       %s
#
# AUTHOR(S):	%s
#               
# PURPOSE:      %s
#
# DATE:         %s
#
#############################################################################
""" % (properties['name'],
       properties['author'],
       properties['desc'],
       time.asctime()))
        
        fd.write(
r"""
import sys
import os
import grass.script as grass
import atexit
""")
        
        # cleanup()
        rast, vect, rast3d, msg = self.model.GetIntermediateData()
        fd.write(
r"""

def cleanup():
""")
        if rast:
            fd.write(
r"""    grass.run_command('g.remove',
                      rast=%s)
""" % ','.join(map(lambda x: "'" + x + "'", rast)))
        if vect:
            fd.write(
r"""    grass.run_command('g.remove',
                      vect = %s)
""" % ','.join(map(lambda x: "'" + x + "'", vect)))
        if rast3d:
            fd.write(
r"""    grass.run_command('g.remove',
                      rast3d = %s)
""" % ','.join(map(lambda x: "'" + x + "'", rast3d)))
        if not rast and not vect and not rast3d:
            fd.write('    pass\n')
        
        fd.write("\ndef main():\n")
        for action in self.model.GetActions():
            task = menuform.GUI().ParseCommand(cmd = action.GetLog(string = False),
                                               show = None)
            opts = task.get_options()
            flags = ''
            params = list()
            strcmd = "    grass.run_command("
            indent = len(strcmd)
            fd.write(strcmd + "'%s',\n" % task.get_name())
            for f in opts['flags']:
                if f.get('value', False) == True:
                    name = f.get('name', '')
                    if len(name) > 1:
                        params.append('%s=True' % name)
                    else:
                        flags += name
            
            for p in opts['params']:
                name = p.get('name', None)
                value = p.get('value', None)
                if name and value:
                    ptype = p.get('type', 'string')
                    if ptype == 'string':
                        params.append("%s='%s'" % (name, value))
                    else:
                        params.append("%s=%s" % (name, value))

            for opt in params[:-1]:
                fd.write("%s%s,\n" % (' ' * indent, opt))
            fd.write("%s%s)\n" % (' ' * indent, params[-1]))
    
        fd.write("\n    return 0\n")
        
        fd.write(
r"""
if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    sys.exit(main())
""")

    def _validateModel(self):
        """!Validate model"""
        self.SetStatusText(_('Validating model...'), 0)
        
        errList = self.model.Validate()
        
        self.SetStatusText('', 0)
        
        return errList
    
    def OnDefineRelation(self, event):
        """!Define relation between data and action items"""
        self.canvas.SetCursor(self.cursors["cross"])
        self.defineRelation = { 'from' : None,
                                'to'   : None }
        
    def OnAddAction(self, event):
        """!Add action to model"""
        if self.searchDialog is None:
            self.searchDialog = ModelSearchDialog(self)
            self.searchDialog.CentreOnParent()
        else:
            self.searchDialog.Reset()
            
        if self.searchDialog.ShowModal() == wx.ID_CANCEL:
            self.searchDialog.Hide()
            return
            
        cmd = self.searchDialog.GetCmd()
        self.searchDialog.Hide()
        
        self.ModelChanged()
        
        # add action to canvas
        width, height = self.canvas.GetSize()
        action = ModelAction(self, cmd = cmd, x = width/2, y = height/2)
        self.canvas.diagram.AddShape(action)
        action.Show(True)

        self._addEvent(action)
        self.model.AddAction(action)
        
        self.canvas.Refresh()
        time.sleep(.1)
        
        # show properties dialog
        win = action.GetPropDialog()
        if not win and action.GetLog(string = False):
            module = menuform.GUI().ParseCommand(action.GetLog(string = False),
                                                 completed = (self.GetOptData, action, action.GetParams()),
                                                 parentframe = self, show = True)
        elif win and not win.IsShown():
            win.Show()
        
        if win:
            win.Raise()

    def OnAddData(self, event):
        """!Add data item to model"""
        # add action to canvas
        width, height = self.canvas.GetSize()
        data = ModelData(self, x = width/2, y = height/2)
        self.canvas.diagram.AddShape(data)
        data.Show(True)
        
        self._addEvent(data)
        self.model.AddData(data)
        
        self.canvas.Refresh()
        
    def OnHelp(self, event):
        """!Display manual page"""
        grass.run_command('g.manual',
                          entry = 'wxGUI.Modeler')

    def OnAbout(self, event):
        """!Display About window"""
        info = wx.AboutDialogInfo()

        info.SetIcon(wx.Icon(os.path.join(globalvar.ETCICONDIR, 'grass.ico'), wx.BITMAP_TYPE_ICO))
        info.SetName(_('wxGUI Graphical Modeler'))
        info.SetWebSite('http://grass.osgeo.org')
        info.SetDescription(_('(C) 2010 by the GRASS Development Team\n\n') + 
                            '\n'.join(textwrap.wrap(_('This program is free software under the GNU General Public License'
                                                      '(>=v2). Read the file COPYING that comes with GRASS for details.'), 75)))
        
        wx.AboutBox(info)
        
    def GetOptData(self, dcmd, layer, params, propwin):
        """!Process action data"""
        if params: # add data items
            for p in params['params']:
                if p.get('prompt', '') in ('raster', 'vector', 'raster3d'):
                    try:
                        name, mapset = p.get('value', '').split('@', 1)
                    except (ValueError, IndexError):
                        continue
                    
                    if mapset != grass.gisenv()['MAPSET']:
                        continue
                    
                    # don't use fully qualified names
                    p['value'] = p.get('value', '').split('@')[0]
                    for idx in range(1, len(dcmd)):
                        if p.get('name', '') in dcmd[idx]:
                            dcmd[idx] = p.get('name', '') + '=' + p.get('value', '')
                            break
            
            width, height = self.canvas.GetSize()
            x = [width/2 + 200, width/2 - 200]
            for p in params['params']:
                if p.get('prompt', '') in ('raster', 'vector', 'raster3d') and \
                        (p.get('value', None) or \
                             p.get('age', 'old') != 'old'):
                    data = layer.FindData(p.get('name', ''))
                    if data:
                        data.SetValue(p.get('value', ''))
                        continue
                    
                    data = self.model.FindData(p.get('value', ''),
                                              p.get('prompt', ''))
                    if data:
                        if p.get('age', 'old') == 'old':
                            rel = ModelRelation(data, layer)
                            data.AddRelation(rel, direction = 'from')
                            self.AddLine(rel)
                        else:
                            rel = ModelRelation(layer, data)
                            data.AddRelation(rel, direction = 'to')
                            self.AddLine(rel)
                        continue
                    
                    data = ModelData(self, name = p.get('name', ''),
                                     value = p.get('value', ''),
                                     prompt = p.get('prompt', ''),
                                     x = x.pop(), y = height/2)
                    layer.AddData(data)
                    self.canvas.diagram.AddShape(data)
                    data.Show(True)
                    
                    self._addEvent(data)
                    self.model.AddData(data)
                    
                    if p.get('age', 'old') == 'old':
                        rel = ModelRelation(data, layer)
                        data.AddRelation(rel, direction = 'from')
                        self.AddLine(rel)
                    else:
                        rel = ModelRelation(layer, data)
                        data.AddRelation(rel, direction = 'to')
                        self.AddLine(rel)
            # valid ?
            valid = True
            for p in params['params']:
                if p.get('value', '') == '' and \
                        p.get('default', '') == '':
                    valid = False
                    break
            
            layer.SetValid(valid)
            
            self.canvas.Refresh()
        
        if dcmd:
            layer.SetProperties(params, propwin)
            
        self.SetStatusText(layer.GetLog(), 0)
        
    def AddLine(self, rel):
        """!Add connection

        @param rel relation
        """
        fromShape = rel.GetFrom()
        toShape   = rel.GetTo()
        
        rel.SetCanvas(self)
        rel.SetPen(wx.BLACK_PEN)
        rel.SetBrush(wx.BLACK_BRUSH)
        rel.AddArrow(ogl.ARROW_ARROW)
        points = rel.GetControlPoints()
        rel.MakeLineControlPoints(2)
        if points:
            for x, y in points:
                rel.InsertLineControlPoint(point = wx.RealPoint(x, y))
            
        self._addEvent(rel)
        
        fromShape.AddLine(rel, toShape)
        
        self.canvas.diagram.AddShape(rel)
        rel.Show(True)
        
    def LoadModelFile(self, filename):
        """!Load model definition stored in GRASS Model XML file (gxm)
        """
        try:
            self.model.LoadModel(filename)
        except GError, e:
            GMessage(parent = self,
                     message = _("Reading model file <%s> failed.\n"
                                 "Invalid file, unable to parse XML document.") % filename)
        
        self.modelFile = filename
        self.SetTitle(self.baseTitle + " - " +  os.path.basename(self.modelFile))
        
        self.SetStatusText(_("Please wait, loading model..."), 0)
        
        # load actions
        for action in self.model.GetActions():
            self._addEvent(action)
            self.canvas.diagram.AddShape(action)
            action.Show(True)
        
        # load data & relations
        for data in self.model.GetData():
            self._addEvent(data)
            self.canvas.diagram.AddShape(data)
            data.Show(True)

            for rel in data.GetRelations():
                self.AddLine(rel)
        
        self.SetStatusText('', 0)
        
        self.canvas.Refresh(True)
        
    def WriteModelFile(self, filename):
        """!Save model to model file, recover original file on error.
        
        @return True on success
        @return False on failure
        """
        tmpfile = tempfile.TemporaryFile(mode='w+b')
        try:
            WriteModelFile(fd = tmpfile,
                           actions = self.model.GetActions(),
                           data = self.model.GetData())
        except StandardError:
            GMessage(parent = self,
                     message = _("Writing current settings to model file failed."))
            return False
        
        try:
            mfile = open(filename, "w")
            tmpfile.seek(0)
            for line in tmpfile.readlines():
                mfile.write(line)
        except IOError:
            wx.MessageBox(parent = self,
                          message = _("Unable to open file <%s> for writing.") % filename,
                          caption = _("Error"),
                          style = wx.OK | wx.ICON_ERROR | wx.CENTRE)
            return False
        
        mfile.close()
        
        return True
    
class ModelCanvas(ogl.ShapeCanvas):
    """!Canvas where model is drawn"""
    def __init__(self, parent):
        self.parent = parent
        ogl.OGLInitialize()
        ogl.ShapeCanvas.__init__(self, parent)
        
        self.diagram = ogl.Diagram()
        self.SetDiagram(self.diagram)
        self.diagram.SetCanvas(self)
        
        self.SetScrollbars(20, 20, 1000/20, 1000/20)
        
        self.Bind(wx.EVT_CHAR,  self.OnChar)
        
    def OnChar(self, event):
        """!Key pressed"""
        kc = event.GetKeyCode()
        diagram = self.GetDiagram()
        if kc == wx.WXK_DELETE:
            self.RemoveSelected()

    def RemoveSelected(self):
        """!Remove selected shapes"""
        self.parent.ModelChanged()
        
        diagram = self.GetDiagram()
        for shape in diagram.GetShapeList():
            if not shape.Selected():
                continue
            self.parent.GetModel().RemoveItem(shape)
            shape.Select(False)
            diagram.RemoveShape(shape)
            
            
        self.Refresh()
        
class ModelAction(ogl.RectangleShape):
    """!Action class (GRASS module)"""
    def __init__(self, parent, x, y, cmd = None, task = None, width = None, height = None):
        self.parent  = parent
        self.task    = task
        if not width:
            width = UserSettings.Get(group='modeler', key='action', subkey=('size', 'width'))
        if not height:
            height = UserSettings.Get(group='modeler', key='action', subkey=('size', 'height'))
        
        if cmd:
            self.task = menuform.GUI().ParseCommand(cmd = cmd,
                                                    show = None)
        else:
            if task:
                self.task = task
            else:
                self.task = None
        
        self.propWin = None
        self.id      = -1    # used for gxm file
        
        self.data = list()   # list of connected data items
        
        self.isValid = False
        
        if self.parent.GetCanvas():
            ogl.RectangleShape.__init__(self, width, height)
            
            self.SetCanvas(self.parent)
            self.SetX(x)
            self.SetY(y)
            self.SetPen(wx.BLACK_PEN)
            self._setBrush(False)
            cmd = self.task.getCmd(ignoreErrors = True)
            if cmd and len(cmd) > 0:
                self.AddText(cmd[0])
            else:
                self.AddText('<<%s>>' % _("module"))
        
    def _setBrush(self, isvalid):
        """!Set brush"""
        if isvalid is None:
            color = UserSettings.Get(group='modeler', key='action',
                                     subkey=('color', 'running'))
        elif isvalid:
            color = UserSettings.Get(group='modeler', key='action',
                                     subkey=('color', 'valid'))
        else:
            color = UserSettings.Get(group='modeler', key='action',
                                     subkey=('color', 'invalid'))
        wxColor = wx.Color(color[0], color[1], color[2])
        self.SetBrush(wx.Brush(wxColor))
        
    def GetId(self):
        """!Get id"""
        return self.id

    def SetId(self, id):
        """!Set id"""
        self.id = id
    
    def SetProperties(self, params, propwin):
        """!Record properties dialog"""
        self.task.params = params['params']
        self.task.flags  = params['flags']
        self.propWin = propwin

    def GetPropDialog(self):
        """!Get properties dialog"""
        return self.propWin

    def GetLog(self, string = True):
        """!Get logging info"""
        cmd = self.task.getCmd(ignoreErrors = True)
        if string:
            if cmd is None:
                return ''
            else:
                return ' '.join(cmd)
        
        return cmd
    
    def GetName(self):
        """!Get name"""
        cmd = self.task.getCmd(ignoreErrors = True)
        if cmd and len(cmd) > 0:
            return cmd[0]
        
        return _('unknown')

    def GetParams(self, dcopy = False):
        """!Get dictionary of parameters"""
        if dcopy:
            return copy.deepcopy(self.task.get_options())
        
        return self.task.get_options()

    def GetTask(self):
        """!Get grassTask instance"""
        return self.task
    
    def SetParams(self, params):
        """!Set dictionary of parameters"""
        self.task.params = params['params']
        self.task.flags  = params['flags']
        
    def MergeParams(self, params):
        """!Merge dictionary of parameters"""
        if params.has_key('flags'):
            for f in params['flags']:
                self.task.set_flag(f['name'],
                                   f.get('value', False))
        if params.has_key('params'):
            for p in params['params']:
                self.task.set_param(p['name'],
                                    p.get('value', ''))
        
    def SetValid(self, isvalid):
        """!Set instance to be valid/invalid"""
        self.isValid = isvalid
        self._setBrush(isvalid)
        
    def AddData(self, item):
        """!Register new data item"""
        if item not in self.data:
            self.data.append(item)
        
    def FindData(self, name):
        """!Find data item by name"""
        for d in self.data:
            if d.GetName() == name:
                return d
        
        return None

    def Update(self, running = False):
        """!Update action"""
        if running:
            self._setBrush(None)
        else:
            self._setBrush(self.isValid)
            
class ModelData(ogl.EllipseShape):
    """!Data item class"""
    def __init__(self, parent, x, y, name = '', value = '', prompt = '', width = None, height = None):
        self.parent  = parent
        self.name    = name
        self.value   = value
        self.prompt  = prompt
        self.intermediate = False
        self.propWin = None
        if not width:
            width = UserSettings.Get(group='modeler', key='data', subkey=('size', 'width'))
        if not height:
            height = UserSettings.Get(group='modeler', key='data', subkey=('size', 'height'))
        
        self.rels = { 'from' : list(), 'to' : list() } # list of recorded relations

        if self.parent.GetCanvas():
            ogl.EllipseShape.__init__(self, width, height)
            
            self.SetCanvas(self.parent)
            self.SetX(x)
            self.SetY(y)
            self.SetPen(wx.BLACK_PEN)
            self._setBrush()
            
            if name:
                self.AddText(name)
            else:
                self.AddText(_('unknown'))
        
            if value:
                self.AddText(value)
            else:
                self.AddText('\n')
        
    def IsIntermediate(self):
        """!Checks if data item is intermediate"""
        return self.intermediate
    
    def SetIntermediate(self, im):
        """!Set intermediate flag"""
        self.intermediate = im
  
    def OnDraw(self, dc):
        pen = self.GetPen()
        if self.intermediate:
            pen.SetStyle(wx.SHORT_DASH)
        else:
            pen.SetStyle(wx.SOLID)
        self.SetPen(pen)
        
        ogl.EllipseShape.OnDraw(self, dc)
        
    def GetLog(self, string = True):
        """!Get logging info"""
        if self.name:
            return self.name + '=' + self.value + ' (' + self.prompt + ')'
        else:
            return _('unknown')

    def GetName(self):
        """!Get name"""
        return self.name

    def GetPrompt(self):
        """!Get prompt"""
        return self.prompt

    def GetValue(self):
        """!Get value"""
        return self.value

    def SetValue(self, value):
        """!Set value"""
        self.value = value
        self.ClearText()
        self.AddText(self.name)
        if value:
            self.AddText(self.value)
        else:
            self.AddText('\n')
        for direction in ('from', 'to'):
            for rel in self.rels[direction]:
                if direction == 'from':
                    action = rel.GetTo()
                else:
                    action = rel.GetFrom()
                
                task = menuform.GUI().ParseCommand(cmd = action.GetLog(string = False),
                                                   show = None)
                task.set_param(self.name, self.value)
                action.SetParams(params = task.get_options())
        
    def GetRelations(self, direction = None):
        """!Get relations from/to"""
        if not direction:
            return self.rels['from'] + self.rels['to']
        
        return self.rels[direction]
        
    def AddRelation(self, rel, direction):
        """!Record new relation

        @param direction direction - 'from' or 'to'
        """
        self.rels[direction].append(rel)
        
    def GetPropDialog(self):
        """!Get properties dialog"""
        return self.propWin

    def SetPropDialog(self, win):
        """!Get properties dialog"""
        self.propWin = win

    def _setBrush(self):
        """!Set brush"""
        if self.prompt == 'raster':
            color = UserSettings.Get(group='modeler', key='data',
                                     subkey=('color', 'raster'))
        elif self.prompt == 'raster3d':
            color = UserSettings.Get(group='modeler', key='data',
                                     subkey=('color', 'raster3d'))
        elif self.prompt == 'vector':
            color = UserSettings.Get(group='modeler', key='data',
                                     subkey=('color', 'vector'))
        else:
            color = UserSettings.Get(group='modeler', key='action',
                                     subkey=('color', 'invalid'))
        wxColor = wx.Color(color[0], color[1], color[2])
        self.SetBrush(wx.Brush(wxColor))
        
    def Update(self):
        """!Update action"""
        self._setBrush()
        
class ModelDataDialog(ElementDialog):
    """!Data item properties dialog"""
    def __init__(self, parent, shape, id = wx.ID_ANY, title = _("Data properties"),
                 style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER):
        self.parent = parent
        self.shape = shape
        prompt = shape.GetPrompt()
        
        if prompt == 'raster':
            label = _('Name of raster map:')
        elif prompt == 'vector':
            label = _('Name of vector map:')
        else:
            label = _('Name of element:')
        
        ElementDialog.__init__(self, parent, title, label = label)
        
        self.element = gselect.Select(parent = self.panel, id = wx.ID_ANY,
                                      size = globalvar.DIALOG_GSELECT_SIZE,
                                      type = prompt)
        self.element.SetValue(shape.GetValue())
        
        self.Bind(wx.EVT_BUTTON, self.OnOK,     self.btnOK)
        self.Bind(wx.EVT_BUTTON, self.OnCancel, self.btnCancel)
        
        self.PostInit()
        
        self._layout()
        self.SetMinSize(self.GetSize())
        
    def _layout(self):
        """!Do layout"""
        self.dataSizer.Add(self.element, proportion=0,
                      flag=wx.EXPAND | wx.ALL, border=1)
        
        self.panel.SetSizer(self.sizer)
        self.sizer.Fit(self)

    def OnOK(self, event):
        """!Ok pressed"""
        self.shape.SetValue(self.GetElement())
        self.parent.canvas.Refresh()
        self.parent.SetStatusText('', 0)
        self.OnCancel(event)
        
    def OnCancel(self, event):
        """!Cancel pressed"""
        self.shape.SetPropDialog(None)
        self.Destroy()
        
class ModelEvtHandler(ogl.ShapeEvtHandler):
    """!Model event handler class"""
    def __init__(self, log, frame):
        ogl.ShapeEvtHandler.__init__(self)
        self.log = log
        self.frame = frame
        self.x = self.y = None
        
    def OnLeftClick(self, x, y, keys = 0, attachment = 0):
        """!Left mouse button pressed -> select item & update statusbar"""
        shape = self.GetShape()
        canvas = shape.GetCanvas()
        dc = wx.ClientDC(canvas)
        canvas.PrepareDC(dc)
        
        if hasattr(self.frame, 'defineRelation'):
            drel = self.frame.defineRelation
            if drel['from'] is None:
                drel['from'] = shape
            elif drel['to'] is None:
                drel['to'] = shape
                rel = ModelRelation(drel['from'], drel['to'])
                self.frame.AddLine(rel)
                del self.frame.defineRelation
        
        if shape.Selected():
            shape.Select(False, dc)
        else:
            redraw = False
            shapeList = canvas.GetDiagram().GetShapeList()
            toUnselect = list()
            
            for s in shapeList:
                if s.Selected():
                    toUnselect.append(s)
            
            shape.Select(True, dc)
            
            for s in toUnselect:
                s.Select(False, dc)
                
        canvas.Refresh(False)

        if hasattr(shape, "GetLog"):
            self.log.SetStatusText(shape.GetLog(), 0)
        
    def OnLeftDoubleClick(self, x, y, keys = 0, attachment = 0):
        """!Left mouse button pressed (double-click) -> show properties"""
        self.OnProperties()
        
    def OnProperties(self, event = None):
        """!Show properties dialog"""
        self.frame.ModelChanged()
        shape = self.GetShape()
        if isinstance(shape, ModelAction):
            module = menuform.GUI().ParseCommand(shape.GetLog(string = False),
                                                 completed = (self.frame.GetOptData, shape, shape.GetParams()),
                                                 parentframe = self.frame, show = True)
        elif isinstance(shape, ModelData):
            dlg = ModelDataDialog(parent = self.frame, shape = shape)
            shape.SetPropDialog(dlg)
            dlg.CentreOnParent()
            dlg.Show()
        
    def OnBeginDragLeft(self, x, y, keys = 0, attachment = 0):
        """!Drag shape"""
        self.frame.ModelChanged()
        if self._previousHandler:
            self._previousHandler.OnBeginDragLeft(x, y, keys, attachment)
        
    def OnRightClick(self, x, y, keys = 0, attachment = 0):
        """!Right click -> pop-up menu"""
        if not hasattr (self, "popupID1"):
            self.popupID1 = wx.NewId()
            self.popupID2 = wx.NewId()
            self.popupID3 = wx.NewId()

        # record coordinates
        self.x = x
        self.y = y
        
        shape = self.GetShape()
        popupMenu = wx.Menu()
        popupMenu.Append(self.popupID1, text=_('Remove'))
        self.frame.Bind(wx.EVT_MENU, self.OnRemove, id = self.popupID1)
        
        if isinstance(shape, ModelRelation):
            popupMenu.AppendSeparator()
            popupMenu.Append(self.popupID2, text=_('Add control point'))
            self.frame.Bind(wx.EVT_MENU, self.OnAddPoint, id = self.popupID2)
            popupMenu.Append(self.popupID3, text=_('Remove control point'))
            self.frame.Bind(wx.EVT_MENU, self.OnRemovePoint, id = self.popupID3)
            if len(shape.GetLineControlPoints()) == 2:
                popupMenu.Enable(self.popupID3, False)
        
        if isinstance(shape, ModelData) and '@' not in shape.GetValue():
            popupMenu.AppendSeparator()
            popupMenu.Append(self.popupID3, text=_('Intermediate'),
                             kind = wx.ITEM_CHECK)
            if self.GetShape().IsIntermediate():
                popupMenu.Check(self.popupID3, True)
            
            self.frame.Bind(wx.EVT_MENU, self.OnIntermediate, id = self.popupID3)
            
        if isinstance(shape, ModelData) or \
                isinstance(shape, ModelAction):
            popupMenu.AppendSeparator()
            popupMenu.Append(self.popupID2, text=_('Properties'))
            self.frame.Bind(wx.EVT_MENU, self.OnProperties, id = self.popupID2)

        self.frame.PopupMenu(popupMenu)
        popupMenu.Destroy()
        
    def OnAddPoint(self, event):
        """!Add control point"""
        shape = self.GetShape()
        shape.InsertLineControlPoint(point = wx.RealPoint(self.x, self.y))
        shape.ResetShapes()
        shape.Select(True)
        self.frame.canvas.Refresh()
        
    def OnRemovePoint(self, event):
        """!Remove control point"""
        shape = self.GetShape()
        shape.DeleteLineControlPoint()
        shape.Select(False)
        shape.Select(True)
        self.frame.canvas.Refresh()
        
    def OnIntermediate(self, event):
        """!Mark data as intermediate"""
        self.frame.ModelChanged()
        shape = self.GetShape()
        shape.SetIntermediate(event.IsChecked())
        self.frame.canvas.Refresh()

    def OnRemove(self, event):
        """!Remove shape
        """
        self.frame.GetCanvas().RemoveSelected()
        
class ModelSearchDialog(wx.Dialog):
    def __init__(self, parent, id = wx.ID_ANY, title = _("Select GRASS module"),
                 style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER, **kwargs):
        """!Graphical modeler module search window
        
        @param parent parent window
        @param id window id
        @param title window title

        @param kwargs wx.Dialogs' arguments
        """
        self.parent = parent
        
        wx.Dialog.__init__(self, parent = parent, id = id, title = title, **kwargs)
        self.SetName("ModelerDialog")
        self.SetIcon(wx.Icon(os.path.join(globalvar.ETCICONDIR, 'grass.ico'), wx.BITMAP_TYPE_ICO))
        
        self.panel = wx.Panel(parent = self, id = wx.ID_ANY)
        
        self.cmdBox = wx.StaticBox(parent = self.panel, id = wx.ID_ANY,
                                   label=" %s " % _("Command"))
        
        self.cmd_prompt = prompt.GPromptSTC(parent = self)
        self.search = SearchModuleWindow(parent = self.panel, cmdPrompt = self.cmd_prompt, showTip = True)
        
        # get commands
        items = self.cmd_prompt.GetCommandItems()
        
        self.btnCancel = wx.Button(self.panel, wx.ID_CANCEL)
        self.btnOk     = wx.Button(self.panel, wx.ID_OK)
        self.btnOk.SetDefault()
        self.btnOk.Enable(False)

        self.cmd_prompt.Bind(wx.EVT_KEY_UP, self.OnText)
        self.Bind(wx.EVT_BUTTON, self.OnOk, self.btnOk)
        
        self._layout()
        
        self.SetSize((500, 275))
        
    def _layout(self):
        btnSizer = wx.StdDialogButtonSizer()
        btnSizer.AddButton(self.btnCancel)
        btnSizer.AddButton(self.btnOk)
        btnSizer.Realize()
        
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.Add(item=self.search, proportion=0,
                      flag=wx.EXPAND | wx.ALL, border=3)
        mainSizer.Add(item=self.cmd_prompt, proportion=1,
                      flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=3)
        mainSizer.Add(item=btnSizer, proportion=0,
                      flag=wx.EXPAND | wx.ALL | wx.ALIGN_CENTER, border=5)
        
        self.panel.SetSizer(mainSizer)
        mainSizer.Fit(self.panel)
        
        self.Layout()

    def GetPanel(self):
        """!Get dialog panel"""
        return self.panel

    def GetCmd(self):
        """!Get command"""
        line = self.cmd_prompt.GetCurLine()[0].strip()
        if len(line) == 0:
            list()
        
        try:
            cmd = shlex.split(str(line))
        except UnicodeError:
            cmd = shlex.split(utils.EncodeString((line)))
            
        return cmd
    
    def OnOk(self, event):
        self.btnOk.SetFocus()
        cmd = self.GetCmd()
        
        if len(cmd) < 1:
            GMessage(parent = self,
                     message = _("Command not defined.\n\n"
                                 "Unable to add new action to the model."))
            return
        
        if cmd[0] not in globalvar.grassCmd['all']:
            GMessage(parent = self,
                     message = _("'%s' is not a GRASS module.\n\n"
                                 "Unable to add new action to the model.") % cmd[0])
            return
        
        self.EndModal(wx.ID_OK)
        
    def OnText(self, event):
        if self.cmd_prompt.AutoCompActive():
            return
        
        entry = self.cmd_prompt.GetTextLeft()
        if len(entry) > 0:
            self.btnOk.Enable()
        else:
            self.btnOk.Enable(False)
            
        event.Skip()
        
    def Reset(self):
        """!Reset dialog"""
        self.search.Reset()
        self.cmd_prompt.OnCmdErase(None)

class ModelRelation(ogl.LineShape):
    """!Data - action relation"""
    def __init__(self, fromShape, toShape):
        self.fromShape = fromShape
        self.toShape   = toShape
        
        self._points    = None
        
        ogl.LineShape.__init__(self)
    
    def GetFrom(self):
        """!Get id of 'from' shape"""
        return self.fromShape
    
    def GetTo(self):
        """!Get id of 'to' shape"""
        return self.toShape
    
    def ResetShapes(self):
        """!Reset related objects"""
        self.fromShape.ResetControlPoints()
        self.toShape.ResetControlPoints()
        self.ResetControlPoints()
        
    def SetControlPoints(self, points):
        """!Set control points"""
        self._points = points
        
    def GetControlPoints(self):
        """!Get list of control points"""
        return self._points
    
class ProcessModelFile:
    """!Process GRASS model file (gxm)"""
    def __init__(self, tree):
        """!A ElementTree handler for the GXM XML file, as defined in
        grass-gxm.dtd.
        """
        self.tree = tree
        self.root = self.tree.getroot()

        # list of actions, data
        self.actions = list()
        self.data    = list()
        
        self._processActions()
        self._processData()
        
    def _filterValue(self, value):
        """!Filter value
        
        @param value
        """
        value = value.replace('&lt;', '<')
        value = value.replace('&gt;', '>')
        
        return value
        
    def _getNodeText(self, node, tag, default = ''):
        """!Get node text"""
        p = node.find(tag)
        if p is not None:
            if p.text:
                return utils.normalize_whitespace(p.text)
            else:
                return ''
        
        return default
    
    def _processActions(self):
        """!Process model file"""
        for action in self.root.findall('action'):
            pos, size = self._getDim(action)
            
            task = action.find('task')
            if task:
                task = self._processTask(task)
            else:
                task = None
            
            aId = int(action.get('id', -1))
            
            self.actions.append({ 'pos'  : pos,
                                  'size' : size,
                                  'task' : task,
                                  'id'   : aId })
            
    def _getDim(self, node):
        """!Get position and size of shape"""
        pos = size = None
        posAttr = node.get('pos', None)
        if posAttr:
            posVal = map(int, posAttr.split(','))
            try:
                pos = (posVal[0], posVal[1])
            except:
                pos = None
        
        sizeAttr = node.get('size', None)
        if sizeAttr:
            sizeVal = map(int, sizeAttr.split(','))
            try:
                size = (sizeVal[0], sizeVal[1])
            except:
                size = None
        
        return pos, size        
    
    def _processData(self):
        """!Process model file"""
        for data in self.root.findall('data'):
            pos, size = self._getDim(data)
            param = data.find('data-parameter')
            name = prompt = value = None
            if param is not None:
                name = param.get('name', None)
                prompt = param.get('prompt', None)
                value = self._filterValue(self._getNodeText(param, 'value'))
            
            if data.find('intermediate') is None:
                intermediate = False
            else:
                intermediate = True
            
            rels = list()
            for rel in data.findall('relation'):
                defrel = { 'id'  : int(rel.get('id', -1)),
                           'dir' : rel.get('dir', 'to') }
                points = list()
                for point in rel.findall('point'):
                    x = self._filterValue(self._getNodeText(point, 'x'))
                    y = self._filterValue(self._getNodeText(point, 'y'))
                    points.append((float(x), float(y)))
                defrel['points'] = points
                rels.append(defrel)
            
            self.data.append({ 'pos' : pos,
                               'size': size,
                               'name' : name,
                               'prompt' : prompt,
                               'value' : value,
                               'intermediate' : intermediate,
                               'rels' : rels })
        
    def _processTask(self, node):
        """!Process task

        @return grassTask instance
        @return None on error
        """
        cmd = list()
        parameterized = list()
        
        name = node.get('name', None)
        if not name:
            return None
        
        cmd.append(name)
        
        # flags
        for f in node.findall('flag'):
            flag = f.get('name', '')
            if f.get('parameterized', '0') == '1':
                parameterized.append(('flag', flag))
                if f.get('value', '1') == '0':
                    continue
            if len(flag) > 1:
                cmd.append('--' + flag)
            else:
                cmd.append('-' + flag)
        # parameters
        for p in node.findall('parameter'):
            name = p.get('name', '')
            if p.find('parameterized') is not None:
                parameterized.append(('param', name))
            cmd.append('%s=%s' % (name,
                                  self._filterValue(self._getNodeText(p, 'value'))))
        
        task = menuform.GUI().ParseCommand(cmd = cmd,
                                           show = None)
        
        for opt, name in parameterized:
            if opt == 'flag':
                task.set_flag(name, True, element = 'parameterized')
            else:
                task.set_param(name, True, element = 'parameterized')
        
        return task
    
class WriteModelFile:
    """!Generic class for writing model file"""
    def __init__(self, fd, actions, data):
        self.fd      = fd
        self.actions = actions
        self.data    = data
        
        self.indent = 0
        
        self._header()
        
        self._actions()
        self._data()
        
        self._footer()

    def _filterValue(self, value):
        """!Make value XML-valid"""
        value = value.replace('<', '&lt;')
        value = value.replace('>', '&gt;')
        
        return value
        
    def _header(self):
        """!Write header"""
        self.fd.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        self.fd.write('<!DOCTYPE gxm SYSTEM "grass-gxm.dtd">\n')
        self.fd.write('%s<gxm>\n' % (' ' * self.indent))
                
    def _footer(self):
        """!Write footer"""
        self.fd.write('%s</gxm>\n' % (' ' * self.indent))
        
    def _actions(self):
        """!Write actions"""
        id = 1
        self.indent += 4
        for action in self.actions:
            action.SetId(id)
            self.fd.write('%s<action id="%d" name="%s" pos="%d,%d" size="%d,%d">\n' % \
                              (' ' * self.indent, id, action.GetName(), action.GetX(), action.GetY(),
                               action.GetWidth(), action.GetHeight()))
            self.indent += 4
            self.fd.write('%s<task name="%s">\n' % (' ' * self.indent, action.GetLog(string = False)[0]))
            self.indent += 4
            for key, val in action.GetParams().iteritems():
                if key == 'flags':
                    for f in val:
                        if f.get('value', False) or f.get('parameterized', False):
                            if f.get('parameterized', False):
                                if f.get('value', False) == False:
                                    self.fd.write('%s<flag name="%s" value="0" parameterized="1" />\n' %
                                                  (' ' * self.indent, f.get('name', '')))
                                else:
                                    self.fd.write('%s<flag name="%s" parameterized="1" />\n' %
                                                  (' ' * self.indent, f.get('name', '')))
                            else:
                                self.fd.write('%s<flag name="%s" />\n' %
                                              (' ' * self.indent, f.get('name', '')))
                else: # parameter
                    for p in val:
                        if not p.get('value', ''):
                            continue
                        self.fd.write('%s<parameter name="%s">\n' %
                                      (' ' * self.indent, p.get('name', '')))
                        self.indent += 4
                        if p.get('parameterized', False):
                            self.fd.write('%s<parameterized />\n' % (' ' * self.indent))
                        self.fd.write('%s<value>%s</value>\n' %
                                      (' ' * self.indent, self._filterValue(p.get('value', ''))))
                        self.indent -= 4
                        self.fd.write('%s</parameter>\n' % (' ' * self.indent))
            self.indent -= 4
            self.fd.write('%s</task>\n' % (' ' * self.indent))
            self.indent -= 4
            self.fd.write('%s</action>\n' % (' ' * self.indent))
            id += 1
        
        self.indent -= 4
        
    def _data(self):
        """!Write data"""
        self.indent += 4
        for data in self.data:
            self.fd.write('%s<data pos="%d,%d" size="%d,%d">\n' % \
                              (' ' * self.indent, data.GetX(), data.GetY(),
                               data.GetWidth(), data.GetHeight()))
            self.indent += 4
            self.fd.write('%s<data-parameter name="%s" prompt="%s">\n' % \
                              (' ' * self.indent, data.GetName(), data.GetPrompt()))
            self.indent += 4
            self.fd.write('%s<value>%s</value>\n' %
                          (' ' * self.indent, self._filterValue(data.GetValue())))
            self.indent -= 4
            self.fd.write('%s</data-parameter>\n' % (' ' * self.indent))
            
            if data.IsIntermediate():
                self.fd.write('%s<intermediate />\n' % (' ' * self.indent))

            # relations
            for ft in ('from', 'to'):
                for rel in data.GetRelations(direction = ft):
                    if ft == 'from':
                        aid = rel.GetTo().GetId()
                    else:
                        aid  = rel.GetFrom().GetId()
                    self.fd.write('%s<relation dir="%s" id="%d">\n' % \
                                      (' ' * self.indent, ft, aid))
                    self.indent += 4
                    for point in rel.GetLineControlPoints()[1:-1]:
                        self.fd.write('%s<point>\n' % (' ' * self.indent))
                        self.indent += 4
                        x, y = point.Get()
                        self.fd.write('%s<x>%f</x>\n' % (' ' * self.indent, x))
                        self.fd.write('%s<y>%f</y>\n' % (' ' * self.indent, y))
                        self.indent -= 4
                        self.fd.write('%s</point>\n' % (' ' * self.indent))
                    self.indent -= 4
                    self.fd.write('%s</relation>\n' % (' ' * self.indent))
                
            self.indent -= 4
            self.fd.write('%s</data>\n' % (' ' * self.indent))
            
class PreferencesDialog(PreferencesBaseDialog):
    """!User preferences dialog"""
    def __init__(self, parent, settings = UserSettings,
                 title = _("Modeler settings")):
        
        PreferencesBaseDialog.__init__(self, parent = parent, title = title,
                                       settings = settings)
        
        # create notebook pages
        self._createActionPage(self.notebook)
        self._createDataPage(self.notebook)
                
        self.SetMinSize(self.GetBestSize())
        self.SetSize(self.size)

    def _createActionPage(self, notebook):
        """!Create notebook page for action settings"""
        panel = wx.Panel(parent = notebook, id = wx.ID_ANY)
        notebook.AddPage(page = panel, text = _("Action"))
        
        # colors
        border = wx.BoxSizer(wx.VERTICAL)
        box   = wx.StaticBox (parent = panel, id = wx.ID_ANY,
                              label = " %s " % _("Color settings"))
        sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        
        gridSizer = wx.GridBagSizer (hgap = 3, vgap = 3)
        gridSizer.AddGrowableCol(0)
        
        row = 0
        gridSizer.Add(item = wx.StaticText(parent = panel, id = wx.ID_ANY,
                                         label = _("Valid:")),
                      flag = wx.ALIGN_LEFT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos = (row, 0))
        vColor = csel.ColourSelect(parent = panel, id = wx.ID_ANY,
                                   colour = self.settings.Get(group='modeler', key='action', subkey=('color', 'valid')),
                                   size = globalvar.DIALOG_COLOR_SIZE)
        vColor.SetName('GetColour')
        self.winId['modeler:action:color:valid'] = vColor.GetId()
        
        gridSizer.Add(item = vColor,
                      flag = wx.ALIGN_RIGHT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos = (row, 1))

        row += 1
        gridSizer.Add(item = wx.StaticText(parent = panel, id = wx.ID_ANY,
                                         label = _("Invalid:")),
                      flag = wx.ALIGN_LEFT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos = (row, 0))
        iColor = csel.ColourSelect(parent = panel, id = wx.ID_ANY,
                                   colour = self.settings.Get(group='modeler', key='action', subkey=('color', 'invalid')),
                                   size = globalvar.DIALOG_COLOR_SIZE)
        iColor.SetName('GetColour')
        self.winId['modeler:action:color:invalid'] = iColor.GetId()
        
        gridSizer.Add(item = iColor,
                      flag = wx.ALIGN_RIGHT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos = (row, 1))

        row += 1
        gridSizer.Add(item = wx.StaticText(parent = panel, id = wx.ID_ANY,
                                         label = _("Running:")),
                      flag = wx.ALIGN_LEFT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos = (row, 0))
        rColor = csel.ColourSelect(parent = panel, id = wx.ID_ANY,
                                   colour = self.settings.Get(group='modeler', key='action', subkey=('color', 'running')),
                                   size = globalvar.DIALOG_COLOR_SIZE)
        rColor.SetName('GetColour')
        self.winId['modeler:action:color:running'] = rColor.GetId()
        
        gridSizer.Add(item = rColor,
                      flag = wx.ALIGN_RIGHT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos = (row, 1))

        sizer.Add(item = gridSizer, proportion = 1, flag = wx.ALL | wx.EXPAND, border = 5)
        border.Add(item = sizer, proportion = 0, flag = wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, border = 3)
        
        # size
        box   = wx.StaticBox (parent = panel, id = wx.ID_ANY,
                              label = " %s " % _("Size settings"))
        sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        
        gridSizer = wx.GridBagSizer (hgap=3, vgap=3)
        gridSizer.AddGrowableCol(0)

        row = 0
        gridSizer.Add(item = wx.StaticText(parent = panel, id = wx.ID_ANY,
                                         label = _("Width:")),
                      flag = wx.ALIGN_LEFT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos = (row, 0))
        
        width = wx.SpinCtrl(parent = panel, id = wx.ID_ANY,
                            min = 0, max = 500,
                            initial = self.settings.Get(group='modeler', key='action', subkey=('size', 'width')))
        width.SetName('GetValue')
        self.winId['modeler:action:size:width'] = width.GetId()
        
        gridSizer.Add(item = width,
                      flag = wx.ALIGN_RIGHT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos = (row, 1))

        row += 1
        gridSizer.Add(item = wx.StaticText(parent=panel, id=wx.ID_ANY,
                                         label=_("Height:")),
                      flag = wx.ALIGN_LEFT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos=(row, 0))
        
        height = wx.SpinCtrl(parent = panel, id = wx.ID_ANY,
                             min = 0, max = 500,
                             initial = self.settings.Get(group='modeler', key='action', subkey=('size', 'height')))
        height.SetName('GetValue')
        self.winId['modeler:action:size:height'] = height.GetId()
        
        gridSizer.Add(item = height,
                      flag = wx.ALIGN_RIGHT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos = (row, 1))
        
        sizer.Add(item=gridSizer, proportion=1, flag=wx.ALL | wx.EXPAND, border=5)
        border.Add(item=sizer, proportion=0, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, border=3)
                
        panel.SetSizer(border)
        
        return panel

    def _createDataPage(self, notebook):
        """!Create notebook page for data settings"""
        panel = wx.Panel(parent = notebook, id = wx.ID_ANY)
        notebook.AddPage(page = panel, text = _("Data"))
        
        # colors
        border = wx.BoxSizer(wx.VERTICAL)
        box   = wx.StaticBox (parent = panel, id = wx.ID_ANY,
                              label = " %s " % _("Color settings"))
        sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        
        gridSizer = wx.GridBagSizer (hgap = 3, vgap = 3)
        gridSizer.AddGrowableCol(0)
        
        row = 0
        gridSizer.Add(item = wx.StaticText(parent = panel, id = wx.ID_ANY,
                                         label = _("Raster:")),
                      flag = wx.ALIGN_LEFT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos = (row, 0))
        rColor = csel.ColourSelect(parent = panel, id = wx.ID_ANY,
                                   colour = self.settings.Get(group='modeler', key='data', subkey=('color', 'raster')),
                                   size = globalvar.DIALOG_COLOR_SIZE)
        rColor.SetName('GetColour')
        self.winId['modeler:data:color:raster'] = rColor.GetId()
        
        gridSizer.Add(item = rColor,
                      flag = wx.ALIGN_RIGHT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos = (row, 1))

        row += 1
        gridSizer.Add(item = wx.StaticText(parent = panel, id = wx.ID_ANY,
                                         label = _("3D raster:")),
                      flag = wx.ALIGN_LEFT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos = (row, 0))
        r3Color = csel.ColourSelect(parent = panel, id = wx.ID_ANY,
                                    colour = self.settings.Get(group='modeler', key='data', subkey=('color', 'raster3d')),
                                    size = globalvar.DIALOG_COLOR_SIZE)
        r3Color.SetName('GetColour')
        self.winId['modeler:data:color:raster3d'] = r3Color.GetId()
        
        gridSizer.Add(item = r3Color,
                      flag = wx.ALIGN_RIGHT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos = (row, 1))
        
        row += 1
        gridSizer.Add(item = wx.StaticText(parent = panel, id = wx.ID_ANY,
                                         label = _("Vector:")),
                      flag = wx.ALIGN_LEFT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos = (row, 0))
        vColor = csel.ColourSelect(parent = panel, id = wx.ID_ANY,
                                   colour = self.settings.Get(group='modeler', key='data', subkey=('color', 'vector')),
                                   size = globalvar.DIALOG_COLOR_SIZE)
        vColor.SetName('GetColour')
        self.winId['modeler:data:color:vector'] = vColor.GetId()
        
        gridSizer.Add(item = vColor,
                      flag = wx.ALIGN_RIGHT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos = (row, 1))
        
        sizer.Add(item = gridSizer, proportion = 1, flag = wx.ALL | wx.EXPAND, border = 5)
        border.Add(item = sizer, proportion = 0, flag = wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, border = 3)

        # size
        box   = wx.StaticBox (parent = panel, id = wx.ID_ANY,
                              label = " %s " % _("Size settings"))
        sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        
        gridSizer = wx.GridBagSizer (hgap=3, vgap=3)
        gridSizer.AddGrowableCol(0)
        
        row = 0
        gridSizer.Add(item = wx.StaticText(parent = panel, id = wx.ID_ANY,
                                         label = _("Width:")),
                      flag = wx.ALIGN_LEFT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos = (row, 0))
        
        width = wx.SpinCtrl(parent = panel, id = wx.ID_ANY,
                            min = 0, max = 500,
                            initial = self.settings.Get(group='modeler', key='data', subkey=('size', 'width')))
        width.SetName('GetValue')
        self.winId['modeler:data:size:width'] = width.GetId()
        
        gridSizer.Add(item = width,
                      flag = wx.ALIGN_RIGHT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos = (row, 1))

        row += 1
        gridSizer.Add(item = wx.StaticText(parent=panel, id=wx.ID_ANY,
                                         label=_("Height:")),
                      flag = wx.ALIGN_LEFT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos=(row, 0))
        
        height = wx.SpinCtrl(parent = panel, id = wx.ID_ANY,
                             min = 0, max = 500,
                             initial = self.settings.Get(group='modeler', key='data', subkey=('size', 'height')))
        height.SetName('GetValue')
        self.winId['modeler:data:size:height'] = height.GetId()
        
        gridSizer.Add(item = height,
                      flag = wx.ALIGN_RIGHT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos = (row, 1))
        
        sizer.Add(item=gridSizer, proportion=1, flag=wx.ALL | wx.EXPAND, border=5)
        border.Add(item=sizer, proportion=0, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, border=3)
        
        panel.SetSizer(border)
        
        return panel

    def OnApply(self, event):
        """!Button 'Apply' pressed"""
        PreferencesBaseDialog.OnApply(self, event)
        
        self.parent.GetModel().Update()
        self.parent.GetCanvas().Refresh()

    def OnSave(self, event):
        """!Button 'Save' pressed"""
        PreferencesBaseDialog.OnSave(self, event)
        
        self.parent.GetModel().Update()
        self.parent.GetCanvas().Refresh()

class PropertiesDialog(wx.Dialog):
    """!Model properties dialog
    """
    def __init__(self, parent, id = wx.ID_ANY,
                 title = _('Model properties'),
                 size = (350, 400),
                 style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER):
        wx.Dialog.__init__(self, parent, id, title, size = size,
                           style = style)
        
        self.metaBox = wx.StaticBox(parent = self, id = wx.ID_ANY,
                                    label=" %s " % _("Metadata"))
        self.cmdBox = wx.StaticBox(parent = self, id = wx.ID_ANY,
                                   label=" %s " % _("Commands"))
        
        self.name = wx.TextCtrl(parent = self, id = wx.ID_ANY,
                                size = (300, 25))
        self.desc = wx.TextCtrl(parent = self, id = wx.ID_ANY,
                                style = wx.TE_MULTILINE,
                                size = (300, 50))
        self.author = wx.TextCtrl(parent = self, id = wx.ID_ANY,
                                size = (300, 25))
        
        # commands
        self.overwrite = wx.CheckBox(parent = self, id=wx.ID_ANY,
                                     label=_("Allow output files to overwrite existing files"))
        self.overwrite.SetValue(UserSettings.Get(group='cmd', key='overwrite', subkey='enabled'))
        
        # buttons
        self.btnOk     = wx.Button(self, wx.ID_OK)
        self.btnCancel = wx.Button(self, wx.ID_CANCEL)
        self.btnOk.SetDefault()
        
        self.btnOk.SetToolTipString(_("Apply properties"))
        self.btnOk.SetDefault()
        self.btnCancel.SetToolTipString(_("Close dialog and ignore changes"))
        
        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        
        self._layout()

    def _layout(self):
        metaSizer = wx.StaticBoxSizer(self.metaBox, wx.VERTICAL)
        gridSizer = wx.GridBagSizer (hgap=3, vgap=3)
        gridSizer.AddGrowableCol(0)
        gridSizer.AddGrowableRow(1)
        gridSizer.Add(item = wx.StaticText(parent = self, id = wx.ID_ANY,
                                         label = _("Name:")),
                      flag = wx.ALIGN_LEFT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos = (0, 0))
        gridSizer.Add(item = self.name,
                      flag = wx.ALIGN_LEFT |
                      wx.ALIGN_CENTER_VERTICAL | wx.EXPAND,
                      pos = (0, 1))
        gridSizer.Add(item = wx.StaticText(parent = self, id = wx.ID_ANY,
                                         label = _("Description:")),
                      flag = wx.ALIGN_LEFT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos = (1, 0))
        gridSizer.Add(item = self.desc,
                      flag = wx.ALIGN_LEFT |
                      wx.ALIGN_CENTER_VERTICAL | wx.EXPAND,
                      pos = (1, 1))
        gridSizer.Add(item = wx.StaticText(parent = self, id = wx.ID_ANY,
                                         label = _("Author(s):")),
                      flag = wx.ALIGN_LEFT |
                      wx.ALIGN_CENTER_VERTICAL,
                      pos = (2, 0))
        gridSizer.Add(item = self.author,
                      flag = wx.ALIGN_LEFT |
                      wx.ALIGN_CENTER_VERTICAL | wx.EXPAND,
                      pos = (2, 1))
        metaSizer.Add(item = gridSizer)
        
        cmdSizer = wx.StaticBoxSizer(self.cmdBox, wx.VERTICAL)
        cmdSizer.Add(item = self.overwrite,
                     flag = wx.EXPAND | wx.ALL, border = 3)
        
        btnStdSizer = wx.StdDialogButtonSizer()
        btnStdSizer.AddButton(self.btnCancel)
        btnStdSizer.AddButton(self.btnOk)
        btnStdSizer.Realize()
        
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.Add(item=metaSizer, proportion=1,
                      flag=wx.EXPAND | wx.ALL, border=5)
        mainSizer.Add(item=cmdSizer, proportion=0,
                      flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=3)
        mainSizer.Add(item=btnStdSizer, proportion=0,
                      flag=wx.EXPAND | wx.ALL | wx.ALIGN_RIGHT, border=5)
        
        self.SetSizer(mainSizer)
        mainSizer.Fit(self)

    def OnCloseWindow(self, event):
        self.Hide()
        
    def GetValues(self):
        """!Get values"""
        return { 'name'   : self.name.GetValue(),
                 'desc'   : self.desc.GetValue(),
                 'author' : self.author.GetValue(),
                 'overwrite' : self.overwrite.IsChecked() }

    def Init(self, prop):
        """!Initialize dialog"""
        self.name.SetValue(prop['name'])
        self.desc.SetValue(prop['desc'])
        self.author.SetValue(prop['author'])
        if prop.has_key('overwrite'):
            self.overwrite.SetValue(prop['overwrite'])

class ModelParamDialog(wx.Dialog):
    def __init__(self, parent, params, id = wx.ID_ANY, title = _("Model parameters"),
                 style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER, **kwargs):
        """!Model parameters dialog
        """
        self.parent = parent
        self.params = params
        
        wx.Dialog.__init__(self, parent = parent, id = id, title = title, style = style, **kwargs)
        
        self.notebook = FN.FlatNotebook(self, id = wx.ID_ANY,
                                        style = FN.FNB_FANCY_TABS |
                                        FN.FNB_BOTTOM |
                                        FN.FNB_NO_NAV_BUTTONS |
                                        FN.FNB_NO_X_BUTTON)
        panel = self._createPages()
        wx.CallAfter(self.notebook.SetSelection, 0)
        
        self.btnCancel = wx.Button(parent = self, id = wx.ID_CANCEL)
        self.btnRun     = wx.Button(parent = self, id = wx.ID_OK,
                                    label = _("&Run"))
        self.btnRun.SetDefault()
        
        self._layout()
        
        size = self.GetBestSize()
        self.SetMinSize(size)
        self.SetSize((size.width, size.height +
                      panel.constrained_size[1] -
                      panel.panelMinHeight))
                
    def _layout(self):
        btnSizer = wx.StdDialogButtonSizer()
        btnSizer.AddButton(self.btnCancel)
        btnSizer.AddButton(self.btnRun)
        btnSizer.Realize()
        
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.Add(item = self.notebook, proportion = 1,
                      flag = wx.EXPAND)
        mainSizer.Add(item=btnSizer, proportion=0,
                      flag=wx.EXPAND | wx.ALL | wx.ALIGN_CENTER, border=5)
        
        self.SetSizer(mainSizer)
        mainSizer.Fit(self)
        
    def _createPages(self):
        """!Create for each parameterized module its own page"""
        nameOrdered = [''] * len(self.params.keys())
        for name, params in self.params.iteritems():
            nameOrdered[params['idx']] =  name
        for name in nameOrdered:
            params = self.params[name]
            panel = self._createPage(name, params)
            self.notebook.AddPage(panel, text = name)
        
        return panel
    
    def _createPage(self, name, params):
        """!Define notebook page"""
        task = menuform.grassTask(name)
        task.flags  = params['flags']
        task.params = params['params']
        
        panel = menuform.cmdPanel(parent = self, id = wx.ID_ANY, task = task)
        
        return panel
    
def main():
    app = wx.PySimpleApp()
    wx.InitAllImageHandlers()
    frame = ModelFrame(parent = None)
    if len(sys.argv) > 1:
        frame.LoadModelFile(sys.argv[1])
    # frame.CentreOnScreen()
    frame.Show()
    
    app.MainLoop()
    
if __name__ == "__main__":
    main()
