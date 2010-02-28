"""!
@package wxgui.py

@brief Main Python app for GRASS wxPython GUI. Main menu, layer management
toolbar, notebook control for display management and access to
command console.

Classes:
 - GMFrame
 - GMApp

(C) 2006-2009 by the GRASS Development Team
This program is free software under the GNU General Public
License (>=v2). Read the file COPYING that comes with GRASS
for details.

@author Michael Barton (Arizona State University)
@author Jachym Cepicky (Mendel University of Agriculture)
@author Martin Landa <landa.martin gmail.com>
"""

import sys
import os
import time
import traceback
import re
import string
import getopt
import platform
import signal

### XML 
try:
    import xml.etree.ElementTree as etree
except ImportError:
    import elementtree.ElementTree as etree # Python <= 2.4

### i18N
import gettext
gettext.install('grasswxpy', os.path.join(os.getenv("GISBASE"), 'locale'), unicode=True)

import gui_modules
gmpath = gui_modules.__path__[0]
sys.path.append(gmpath)

import images
imagepath = images.__path__[0]
sys.path.append(imagepath)

import icons
gmpath = icons.__path__[0]
sys.path.append(gmpath)

import gui_modules.globalvar as globalvar
if not os.getenv("GRASS_WXBUNDLED"):
    globalvar.CheckForWx()

import wx
import wx.aui
import wx.combo
import wx.html
import wx.stc
import wx.lib.agw.customtreectrl as CT
import wx.lib.flatnotebook as FN

grassPath = os.path.join(globalvar.ETCDIR, "python")
sys.path.append(grassPath)
from grass.script import core as grass

import gui_modules.utils as utils
import gui_modules.preferences as preferences
import gui_modules.wxgui_utils as wxgui_utils
import gui_modules.mapdisp as mapdisp
import gui_modules.menudata as menudata
import gui_modules.menuform as menuform
import gui_modules.histogram as histogram
import gui_modules.profile as profile
import gui_modules.rules as rules
import gui_modules.mcalc_builder as mapcalculator
import gui_modules.gcmd as gcmd
import gui_modules.georect as georect
import gui_modules.dbm as dbm
import gui_modules.workspace as workspace
import gui_modules.goutput as goutput
import gui_modules.gdialogs as gdialogs
import gui_modules.colorrules as colorrules
import gui_modules.ogc_services as ogc_services
import gui_modules.prompt as prompt
from   gui_modules.debug import Debug
from   gui_modules.help import MenuTreeWindow
from   gui_modules.help import AboutWindow
from   icons.icon import Icons

UserSettings = preferences.globalSettings

class GMFrame(wx.Frame):
    """!
    GIS Manager frame with notebook widget for controlling
    GRASS GIS. Includes command console page for typing GRASS
    (and other) commands, tree widget page for managing map layers.
    """
    def __init__(self, parent, id=wx.ID_ANY, title=_("GRASS GIS Layer Manager"),
                 workspace=None):
        self.parent    = parent
        self.baseTitle = title
        self.iconsize  = (16, 16)

        wx.Frame.__init__(self, parent=parent, id=id, size=(550, 450),
                          style=wx.DEFAULT_FRAME_STYLE)
                          
        self.SetTitle(self.baseTitle)
        self.SetName("LayerManager")

        self.SetIcon(wx.Icon(os.path.join(globalvar.ETCICONDIR, 'grass.ico'), wx.BITMAP_TYPE_ICO))

        self._auimgr = wx.aui.AuiManager(self)

        # initialize variables
        self.disp_idx      = 0            # index value for map displays and layer trees
        self.curr_page     = ''           # currently selected page for layer tree notebook
        self.curr_pagenum  = ''           # currently selected page number for layer tree notebook
        self.workspaceFile = workspace    # workspace file
        self.menucmd       = dict()       # menuId / cmd
        self.georectifying = None         # reference to GCP class or None
        # list of open dialogs
        self.dialogs        = dict()
        self.dialogs['preferences'] = None
        self.dialogs['atm'] = list()
        
        # creating widgets
        # -> self.notebook, self.goutput, self.outpage
        self.menubar, self.menudata = self.__createMenuBar()
        self.statusbar = self.CreateStatusBar(number=1)
        self.notebook  = self.__createNoteBook()
        self.toolbar   = self.__createToolBar()
        
        # bindings
        self.Bind(wx.EVT_CLOSE,    self.OnCloseWindow)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)

        # minimal frame size
        self.SetMinSize((500, 400))

        # AUI stuff
        self._auimgr.AddPane(self.notebook, wx.aui.AuiPaneInfo().
                             Left().CentrePane().BestSize((-1,-1)).Dockable(False).
                             CloseButton(False).DestroyOnClose(True).Row(1).Layer(0))

        self._auimgr.Update()

        wx.CallAfter(self.notebook.SetSelection, 0)
        
        # use default window layout ?
        if UserSettings.Get(group='general', key='defWindowPos', subkey='enabled') is True:
            dim = UserSettings.Get(group='general', key='defWindowPos', subkey='dim')
            try:
               x, y = map(int, dim.split(',')[0:2])
               w, h = map(int, dim.split(',')[2:4])
               self.SetPosition((x, y))
               self.SetSize((w, h))
            except:
                pass

        self.Show()

        # load workspace file if requested
        if (self.workspaceFile):
            # load given workspace file
            if self.LoadWorkspaceFile(self.workspaceFile):
                self.SetTitle(self.baseTitle + " - " +  os.path.basename(self.workspaceFile))
            else:
                self.workspaceFile = None
        else:
            # start default initial display
            self.NewDisplay(show=False)

        # show map display widnow
        # -> OnSize() -> UpdateMap()
        if self.curr_page and not self.curr_page.maptree.mapdisplay.IsShown():
            self.curr_page.maptree.mapdisplay.Show()
        
        # redirect stderr to log area    
        self.goutput.Redirect()
        # fix goutput's pane size
        self.goutput.SetSashPosition(int(self.GetSize()[1] * .45))
        
        # start with layer manager on top
        self.curr_page.maptree.mapdisplay.Raise()
        self.Raise()
            
    def __createMenuBar(self):
        """!Creates menubar"""

        self.menubar = wx.MenuBar()
        self.menudata = menudata.Data()
        for eachMenuData in self.menudata.GetMenu():
            for eachHeading in eachMenuData:
                menuLabel = eachHeading[0]
                menuItems = eachHeading[1]
                self.menubar.Append(self.__createMenu(menuItems), menuLabel)
        self.SetMenuBar(self.menubar)

        return (self.menubar, self.menudata)

    def __createMenu(self, menuData):
        """!Creates menu"""

        menu = wx.Menu()
        for eachItem in menuData:
            if len(eachItem) == 2:
                label = eachItem[0]
                subMenu = self.__createMenu(eachItem[1])
                menu.AppendMenu(wx.ID_ANY, label, subMenu)
            else:
                self.__createMenuItem(menu, *eachItem)
        self.Bind(wx.EVT_MENU_HIGHLIGHT_ALL, self.OnMenuHighlight)
        return menu

    def __createMenuItem(self, menu, label, help, handler, gcmd, keywords, shortcut = '', kind = wx.ITEM_NORMAL):
        """!Creates menu items"""

        if not label:
            menu.AppendSeparator()
            return

        if len(gcmd) > 0:
            helpString = gcmd + ' -- ' + help
        else:
            helpString = help
        
        if shortcut:
            label += '\t' + shortcut
        
        menuItem = menu.Append(wx.ID_ANY, label, helpString, kind)

        self.menucmd[menuItem.GetId()] = gcmd

        if len(gcmd) > 0 and \
                gcmd.split()[0] not in globalvar.grassCmd['all']:
            menuItem.Enable (False)

        rhandler = eval(handler)

        self.Bind(wx.EVT_MENU, rhandler, menuItem)

    def __createNoteBook(self):
        """!Creates notebook widgets"""

        #create main notebook widget
        nbStyle = FN.FNB_FANCY_TABS | \
            FN.FNB_BOTTOM | \
            FN.FNB_NO_NAV_BUTTONS | \
            FN.FNB_NO_X_BUTTON
        
        self.notebook = FN.FlatNotebook(parent=self, id=wx.ID_ANY, style=nbStyle)

        #self.notebook = wx.aui.AuiNotebook(parent=self, id=wx.ID_ANY, style=wx.aui.AUI_NB_BOTTOM)
        #self.notebook.SetFont(wx.Font(pointSize=11, family=wx.FONTFAMILY_DEFAULT, style=wx.NORMAL, weight=0))

        # create displays notebook widget and add it to main notebook page
        cbStyle = globalvar.FNPageStyle
        self.gm_cb = FN.FlatNotebook(self, id=wx.ID_ANY, style=cbStyle)
        self.gm_cb.SetTabAreaColour(globalvar.FNPageColor)
        self.notebook.AddPage(self.gm_cb, text=_("Map layers for each display"))

        # create command output text area and add it to main notebook page
        self.goutput = goutput.GMConsole(self, pageid=1)
        self.outpage = self.notebook.AddPage(self.goutput, text=_("Command console"))

        # bindings
        self.gm_cb.Bind(FN.EVT_FLATNOTEBOOK_PAGE_CHANGED, self.OnCBPageChanged)
        self.notebook.Bind(FN.EVT_FLATNOTEBOOK_PAGE_CHANGED, self.OnPageChanged)
        self.gm_cb.Bind(FN.EVT_FLATNOTEBOOK_PAGE_CLOSING, self.OnCBPageClosed)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(item=self.goutput, proportion=1,
                  flag=wx.EXPAND | wx.ALL, border=1)
        self.SetSizer(sizer)
#        self.out_sizer.Fit(self.outpage)
        self.Layout()

        self.Centre()
        return self.notebook

    def __createToolBar(self):
        """!Creates toolbar"""

        self.toolbar = self.CreateToolBar()
        self.toolbar.SetToolBitmapSize(globalvar.toolbarSize)

        for each in self.ToolbarData():
            self.AddToolbarButton(self.toolbar, *each)
        self.toolbar.Realize()

        return self.toolbar

    def OnMenuHighlight(self, event):
        """
        Default menu help handler
        """
         # Show how to get menu item info from this event handler
        id = event.GetMenuId()
        item = self.GetMenuBar().FindItemById(id)
        if item:
            text = item.GetText()
            help = item.GetHelp()

        # but in this case just call Skip so the default is done
        event.Skip()

    def OnGeorectify(self, event):
        """
        Launch georectifier module
        """
        georect.GeorectWizard(self)
        
    def OnMapsets(self, event):
        """
        Launch mapset access dialog
        """
        dlg = preferences.MapsetAccess(parent=self, id=wx.ID_ANY)
        dlg.CenterOnScreen()

        # if OK is pressed...
        if dlg.ShowModal() == wx.ID_OK:
            ms = dlg.GetMapsets()
            # run g.mapsets with string of accessible mapsets
            gcmd.RunCommand('g.mapsets',
                            parent = self,
                            mapset = '%s' % ','.join(ms))
            
    def OnRDigit(self, event):
        """
        Launch raster digitizing module
        """
        pass

    def OnCBPageChanged(self, event):
        """!Page in notebook (display) changed"""
        old_pgnum = event.GetOldSelection()
        new_pgnum = event.GetSelection()
        
        self.curr_page   = self.gm_cb.GetCurrentPage()
        self.curr_pagenum = self.gm_cb.GetSelection()
        
        try:
            self.curr_page.maptree.mapdisplay.SetFocus()
            self.curr_page.maptree.mapdisplay.Raise()
        except:
            pass
        
        event.Skip()

    def OnPageChanged(self, event):
        """!Page in notebook changed"""
        page = event.GetSelection()
        if page == self.goutput.pageid:
            # remove '(...)'
            self.notebook.SetPageText(page, _("Command console"))
            self.goutput.cmd_prompt.SetSTCFocus(True)
            
        event.Skip()

    def OnCBPageClosed(self, event):
        """
        Page of notebook closed
        Also close associated map display
        """
        if UserSettings.Get(group='manager', key='askOnQuit', subkey='enabled'):
            maptree = self.curr_page.maptree
            
            if self.workspaceFile:
                message = _("Do you want to save changes in the workspace?")
            else:
                message = _("Do you want to store current settings "
                            "to workspace file?")
            
            # ask user to save current settings
            if maptree.GetCount() > 0:
                dlg = wx.MessageDialog(self,
                                       message=message,
                                       caption=_("Close Map Display %d") % (self.curr_pagenum + 1),
                                       style=wx.YES_NO | wx.YES_DEFAULT |
                                       wx.CANCEL | wx.ICON_QUESTION | wx.CENTRE)
                ret = dlg.ShowModal()
                if ret == wx.ID_YES:
                    if not self.workspaceFile:
                        self.OnWorkspaceSaveAs()
                    else:
                        self.SaveToWorkspaceFile(self.workspaceFile)
                elif ret == wx.ID_CANCEL:
                    event.Veto()
                    dlg.Destroy()
                    return
                dlg.Destroy()

        self.gm_cb.GetPage(event.GetSelection()).maptree.Map.Clean()
        self.gm_cb.GetPage(event.GetSelection()).maptree.Close(True)

        self.curr_page = None

        event.Skip()

    def GetLogWindow(self):
        """!Get widget for command output"""
        return self.goutput
    
    def GetMenuCmd(self, event):
        """!Get GRASS command from menu item

        Return command as a list"""
        layer = None
        
        if event:
            cmd = self.menucmd[event.GetId()]
        
        try:
            cmdlist = cmd.split(' ')
        except: # already list?
            cmdlist = cmd
            
        # check list of dummy commands for GUI modules that do not have GRASS
        # bin modules or scripts. 
        if cmd in ['vcolors']:
            return cmdlist

        try:
            layer = self.curr_page.maptree.layer_selected
            name = self.curr_page.maptree.GetPyData(layer)[0]['maplayer'].name
            type = self.curr_page.maptree.GetPyData(layer)[0]['type']
        except:
            layer = None
        if layer and len(cmdlist) == 1: # only if no paramaters given
            if (type == 'raster' and cmdlist[0][0] == 'r' and cmdlist[0][1] != '3') or \
                    (type == 'vector' and cmdlist[0][0] == 'v'):
                input = menuform.GUI().GetCommandInputMapParamKey(cmdlist[0])
                if input:
                    cmdlist.append("%s=%s" % (input, name))

        return cmdlist

    def RunMenuCmd(self, event, cmd = ''):
        """!Run command selected from menu"""
        if event:
            cmd = self.GetMenuCmd(event)
        self.goutput.RunCmd(cmd, switchPage=False)

    def OnMenuCmd(self, event, cmd = ''):
        """!Parse command selected from menu"""
        if event:
            cmd = self.GetMenuCmd(event)
        menuform.GUI().ParseCommand(cmd, parentframe=self)

    def OnRunScript(self, event):
        """!Run script"""
        # open dialog and choose script file
        dlg = wx.FileDialog(parent = self, message = _("Choose script file"),
                            defaultDir = os.getcwd(), wildcard = _("Bash script (*.sh)|*.sh|Python script (*.py)|*.py"))
        
        filename = None
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetPath()
        
        if not filename:
            return False

        if not os.path.exists(filename):
            wx.MessageBox(parent = self,
                          message = _("Script file '%s' doesn't exist. Operation cancelled.") % filename,
                          caption = _("Error"), style=wx.OK | wx.ICON_ERROR | wx.CENTRE)
            return
        
        self.goutput.WriteCmdLog(_("Launching script '%s'...") % filename)
        self.goutput.RunCmd(filename, switchPage = True)
        
    def OnChangeLocation(self, event):
        """Change current location"""
        dlg = gdialogs.LocationDialog(parent = self)
        if dlg.ShowModal() == wx.ID_OK:
            location, mapset = dlg.GetValues()
            if location and mapset:
                ret = gcmd.RunCommand("g.gisenv",
                                      set = "LOCATION_NAME=%s" % location)
                ret += gcmd.RunCommand("g.gisenv",
                                       set = "MAPSET=%s" % mapset)
                if ret > 0:
                    wx.MessageBox(parent = self,
                                  message = _("Unable to switch to location <%(loc)s> mapset <%(mapset)s>.") % \
                                      { 'loc' : location, 'mapset' : mapset },
                                  caption = _("Error"), style = wx.OK | wx.ICON_ERROR | wx.CENTRE)
                else:
                    # close workspace
                    self.OnWorkspaceClose()
                    self.OnWorkspaceNew()
                    wx.MessageBox(parent = self,
                                  message = _("Current location is <%(loc)s>.\n"
                                              "Current mapset is <%(mapset)s>.") % \
                                      { 'loc' : location, 'mapset' : mapset },
                                  caption = _("Info"), style = wx.OK | wx.ICON_INFORMATION | wx.CENTRE)
                    
    def OnChangeMapset(self, event):
        """Change current mapset"""
        dlg = gdialogs.MapsetDialog(parent = self)
        if dlg.ShowModal() == wx.ID_OK:
            mapset = dlg.GetMapset()
            if mapset:
                if gcmd.RunCommand("g.gisenv",
                                   set = "MAPSET=%s" % mapset) != 0:
                    wx.MessageBox(parent = self,
                                  message = _("Unable to switch to mapset <%s>.") % mapset,
                                  caption = _("Error"), style = wx.OK | wx.ICON_ERROR | wx.CENTRE)
                else:
                    wx.MessageBox(parent = self,
                                  message = _("Current mapset is <%s>.") % mapset,
                                  caption = _("Info"), style = wx.OK | wx.ICON_INFORMATION | wx.CENTRE)
        
    def OnNewVector(self, event):
        """!Create new vector map layer"""
        name, add = gdialogs.CreateNewVector(self, log = self.goutput,
                                             cmd = (('v.edit',
                                                     { 'tool' : 'create' },
                                                     'map')))
        
        if name and add:
            # add layer to map layer tree
            self.curr_page.maptree.AddLayer(ltype='vector',
                                            lname=name,
                                            lchecked=True,
                                            lopacity=1.0,
                                            lcmd=['d.vect', 'map=%s' % name])
           
    def OnMenuTree(self, event):
        """!Show dialog with menu tree"""
        dlg = MenuTreeWindow(self)
        dlg.CentreOnScreen()
        dlg.Show()
    
    def OnAboutGRASS(self, event):
        """!Display 'About GRASS' dialog"""
        win = AboutWindow(self)
        win.CentreOnScreen()
        win.Show(True)  
        
    def OnWorkspace(self, event):
        """!Workspace menu (new, load)"""
        point = wx.GetMousePosition()
        menu = wx.Menu()

        # Add items to the menu
        new = wx.MenuItem(menu, wx.ID_ANY, Icons["workspaceNew"].GetLabel())
        new.SetBitmap(Icons["workspaceNew"].GetBitmap(self.iconsize))
        menu.AppendItem(new)
        self.Bind(wx.EVT_MENU, self.OnWorkspaceNew, new)

        load = wx.MenuItem(menu, wx.ID_ANY, Icons["workspaceLoad"].GetLabel())
        load.SetBitmap(Icons["workspaceLoad"].GetBitmap(self.iconsize))
        menu.AppendItem(load)
        self.Bind(wx.EVT_MENU, self.OnWorkspaceLoad, load)

        # create menu
        self.PopupMenu(menu)
        menu.Destroy()

    def OnWorkspaceNew(self, event=None):
        """!Create new workspace file

        Erase current workspace settings first"""

        Debug.msg(4, "GMFrame.OnWorkspaceNew():")
        
        # start new map display if no display is available
        if not self.curr_page:
            self.NewDisplay()
        
        maptree = self.curr_page.maptree
        
        # ask user to save current settings
        if maptree.GetCount() > 0:
             dlg = wx.MessageDialog(self, message=_("Current workspace is not empty. "
                                                    "Do you want to store current settings "
                                                    "to workspace file?"),
                                    caption=_("Create new workspace?"),
                                    style=wx.YES_NO | wx.YES_DEFAULT | \
                                        wx.CANCEL | wx.ICON_QUESTION)
             ret = dlg.ShowModal()
             if ret == wx.ID_YES:
                 self.OnWorkspaceSaveAs()
             elif ret == wx.ID_CANCEL:
                 dlg.Destroy()
                 return
             
             dlg.Destroy()
        
        # delete all items
        maptree.DeleteAllItems()
        
        # add new root element
        maptree.root = maptree.AddRoot("Map Layers")
        self.curr_page.maptree.SetPyData(maptree.root, (None,None))
        
        # no workspace file loaded
        self.workspaceFile = None
        self.SetTitle(self.baseTitle)
        
    def OnWorkspaceOpen(self, event=None):
        """!Open file with workspace definition"""
        dlg = wx.FileDialog(parent=self, message=_("Choose workspace file"),
                            defaultDir=os.getcwd(), wildcard=_("GRASS Workspace File (*.gxw)|*.gxw"))

        filename = ''
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetPath()

        if filename == '':
            return

        Debug.msg(4, "GMFrame.OnWorkspaceOpen(): filename=%s" % filename)

        # delete current layer tree content
        self.OnWorkspaceClose()
        
        self.LoadWorkspaceFile(filename)

        self.workspaceFile = filename
        self.SetTitle(self.baseTitle + " - " +  os.path.basename(self.workspaceFile))

    def LoadWorkspaceFile(self, filename):
        """!Load layer tree definition stored in GRASS Workspace XML file (gxw)

        @todo Validate against DTD
        
        @return True on success
        @return False on error
        """
        # dtd
        dtdFilename = os.path.join(globalvar.ETCWXDIR, "xml", "grass-gxw.dtd")
        
        # parse workspace file
        try:
            gxwXml = workspace.ProcessWorkspaceFile(etree.parse(filename))
        except Exception, err:
            raise gcmd.GStdError(_("Reading workspace file <%(file)s> failed.\n"
                                   "Invalid file, unable to parse XML document."
                                   "\n\n%(err)s") % { 'file' : filename, 'err': err},
                                 parent = self)
        
        busy = wx.BusyInfo(message=_("Please wait, loading workspace..."),
                           parent=self)
        wx.Yield()

        #
        # load layer manager window properties
        #
        if UserSettings.Get(group='workspace', key='posManager', subkey='enabled') is False:
            if gxwXml.layerManager['pos']:
                self.SetPosition(gxwXml.layerManager['pos'])
            if gxwXml.layerManager['size']:
                self.SetSize(gxwXml.layerManager['size'])
        
        #
        # start map displays first (list of layers can be empty)
        #
        displayId = 0
        mapdisplay = list()
        for display in gxwXml.displays:
            mapdisp = self.NewDisplay(show=False)
            mapdisplay.append(mapdisp)
            maptree = self.gm_cb.GetPage(displayId).maptree
            
            # set windows properties
            mapdisp.SetProperties(render=display['render'],
                                  mode=display['mode'],
                                  showCompExtent=display['showCompExtent'],
                                  constrainRes=display['constrainRes'],
                                  projection=display['projection']['enabled'])

            if display['projection']['enabled']:
                if display['projection']['epsg']:
                    UserSettings.Set(group = 'display', key = 'projection', subkey = 'epsg',
                                     value = display['projection']['epsg'])
                    if display['projection']['proj']:
                        UserSettings.Set(group = 'display', key = 'projection', subkey = 'proj4',
                                         value = display['projection']['proj'])
            
            # set position and size of map display
            if UserSettings.Get(group='workspace', key='posDisplay', subkey='enabled') is False:
                if display['pos']:
                    mapdisp.SetPosition(display['pos'])
                if display['size']:
                    mapdisp.SetSize(display['size'])
                    
            # set extent if defined
            if display['extent']:
                w, s, e, n = display['extent']
                region = maptree.Map.region = maptree.Map.GetRegion(w=w, s=s, e=e, n=n)
                mapdisp.GetWindow().ResetZoomHistory()
                mapdisp.GetWindow().ZoomHistory(region['n'],
                                                region['s'],
                                                region['e'],
                                                region['w'])
                
            mapdisp.Show()
            
            displayId += 1
    
        maptree = None 
        selected = [] # list of selected layers
        # 
        # load list of map layers
        #
        for layer in gxwXml.layers:
            display = layer['display']
            maptree = self.gm_cb.GetPage(display).maptree
            
            newItem = maptree.AddLayer(ltype=layer['type'],
                                       lname=layer['name'],
                                       lchecked=layer['checked'],
                                       lopacity=layer['opacity'],
                                       lcmd=layer['cmd'],
                                       lgroup=layer['group'],
                                       lnviz=layer['nviz'],
                                       lvdigit=layer['vdigit'])
            
            if layer.has_key('selected'):
                if layer['selected']:
                    selected.append((maptree, newItem))
                else:
                    maptree.SelectItem(newItem, select=False)
            
        for maptree, layer in selected:
            if not maptree.IsSelected(layer):
                maptree.SelectItem(layer, select=True)
                maptree.layer_selected = layer
                
        busy.Destroy()
        
        if maptree:
            # reverse list of map layers
            maptree.Map.ReverseListOfLayers()

        for mdisp in mapdisplay:
            mdisp.MapWindow2D.UpdateMap()

        return True

    def OnWorkspaceLoad(self, event=None):
        """!Load given map layers into layer tree"""
        dialog = gdialogs.LoadMapLayersDialog(parent=self, title=_("Load map layers into layer tree"))

        if dialog.ShowModal() == wx.ID_OK:
            # start new map display if no display is available
            if not self.curr_page:
                self.NewDisplay()

            maptree = self.curr_page.maptree
            busy = wx.BusyInfo(message=_("Please wait, loading workspace..."),
                               parent=self)
            wx.Yield()
            
            for layerName in dialog.GetMapLayers():
                if dialog.GetLayerType() == 'raster':
                    cmd = ['d.rast', 'map=%s' % layerName]
                elif dialog.GetLayerType() == 'vector':
                    cmd = ['d.vect', 'map=%s' % layerName]
                newItem = maptree.AddLayer(ltype=dialog.GetLayerType(),
                                           lname=layerName,
                                           lchecked=False,
                                           lopacity=1.0,
                                           lcmd=cmd,
                                           lgroup=None)

            busy.Destroy()

    def OnWorkspaceLoadGrcFile(self, event):
        """!Load map layers from GRC file (Tcl/Tk GUI) into map layer tree"""
        dlg = wx.FileDialog(parent=self, message=_("Choose GRC file to load"),
                            defaultDir=os.getcwd(), wildcard=_("Old GRASS Workspace File (*.grc)|*.grc"))

        filename = ''
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetPath()

        if filename == '':
            return

        Debug.msg(4, "GMFrame.OnWorkspaceLoadGrcFile(): filename=%s" % filename)

        # start new map display if no display is available
        if not self.curr_page:
            self.NewDisplay()

        busy = wx.BusyInfo(message=_("Please wait, loading workspace..."),
                           parent=self)
        wx.Yield()

        maptree = None
        for layer in workspace.ProcessGrcFile(filename).read(self):
            maptree = self.gm_cb.GetPage(layer['display']).maptree
            newItem = maptree.AddLayer(ltype=layer['type'],
                                       lname=layer['name'],
                                       lchecked=layer['checked'],
                                       lopacity=layer['opacity'],
                                       lcmd=layer['cmd'],
                                       lgroup=layer['group'])

            busy.Destroy()
            
        if maptree:
            # reverse list of map layers
            maptree.Map.ReverseListOfLayers()

    def OnWorkspaceSaveAs(self, event=None):
        """!Save workspace definition to selected file"""

        dlg = wx.FileDialog(parent=self, message=_("Choose file to save current workspace"),
                            defaultDir=os.getcwd(), wildcard=_("GRASS Workspace File (*.gxw)|*.gxw"), style=wx.FD_SAVE)

        filename = ''
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetPath()

        if filename == '':
            return False

        # check for extension
        if filename[-4:] != ".gxw":
            filename += ".gxw"

        if os.path.exists(filename):
            dlg = wx.MessageDialog(self, message=_("Workspace file <%s> already exists. "
                                                   "Do you want to overwrite this file?") % filename,
                                   caption=_("Save workspace"), style=wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
            if dlg.ShowModal() != wx.ID_YES:
                dlg.Destroy()
                return False

        Debug.msg(4, "GMFrame.OnWorkspaceSaveAs(): filename=%s" % filename)

        self.SaveToWorkspaceFile(filename)
        self.workspaceFile = filename
        self.SetTitle(self.baseTitle + " - " + os.path.basename(self.workspaceFile))

    def OnWorkspaceSave(self, event=None):
        """!Save file with workspace definition"""

        if self.workspaceFile:
            dlg = wx.MessageDialog(self, message=_("Workspace file <%s> already exists. "
                                                   "Do you want to overwrite this file?") % \
                                       self.workspaceFile,
                                   caption=_("Save workspace"), style=wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
            if dlg.ShowModal() == wx.ID_NO:
                dlg.Destroy()
            else:
                Debug.msg(4, "GMFrame.OnWorkspaceSave(): filename=%s" % self.workspaceFile)
                self.SaveToWorkspaceFile(self.workspaceFile)
        else:
            self.OnWorkspaceSaveAs()

    def SaveToWorkspaceFile(self, filename):
        """!Save layer tree layout to workspace file

        Return True on success, False on error
        """

        try:
            file = open(filename, "w")
        except IOError:
            wx.MessageBox(parent=self,
                          message=_("Unable to open workspace file <%s> for writing.") % filename,
                          caption=_("Error"), style=wx.OK | wx.ICON_ERROR | wx.CENTRE)
            return False

        try:
            workspace.WriteWorkspaceFile(lmgr=self, file=file)
        except StandardError, e:
            file.close()
            wx.MessageBox(parent=self,
                          message=_("Writing current settings to workspace file failed (%s)." % e),
                          caption=_("Error"),
                          style=wx.OK | wx.ICON_ERROR | wx.CENTRE)
            return False

        file.close()
        
        return True
    
    def OnWorkspaceClose(self, event=None):
        """!Close file with workspace definition

        If workspace has been modified ask user to save the changes.
        """

        Debug.msg(4, "GMFrame.OnWorkspaceClose(): file=%s" % self.workspaceFile)
        self.workspaceFile = None
        self.SetTitle(self.baseTitle)

        displays = []
        for page in range(0, self.gm_cb.GetPageCount()):
            displays.append(self.gm_cb.GetPage(page).maptree.mapdisplay)
        
        for display in displays:
            display.OnCloseWindow(event)
        
        self.disp_idx = 0
        self.curr_page = None
        

    def RulesCmd(self, event, cmd = ''):
        """
        Launches dialog for commands that need rules
        input and processes rules
        """
        if event:
            cmd = self.GetMenuCmd(event)
                
        if cmd[0] == 'r.colors' or cmd[0] == 'vcolors':
            ctable = colorrules.ColorTable(self, cmd=cmd[0])
            ctable.Show()
        else:
            dlg = rules.RulesText(self, cmd=cmd)
            dlg.CenterOnScreen()
            if dlg.ShowModal() == wx.ID_OK:
                gtemp = utils.GetTempfile()
                output = open(gtemp, "w")
                try:
                    output.write(dlg.rules)
                finally:
                    output.close()
    
                cmdlist = [cmd[0],
                           'input=%s' % dlg.inmap,
                           'output=%s' % dlg.outmap,
                           'rules=%s' % gtemp]
    
                if dlg.overwrite == True:
                    cmdlist.append('--o')
    
                dlg.Destroy()
    
                self.goutput.RunCmd(cmdlist)

    def OnPreferences(self, event):
        """!General GUI preferences/settings"""
        if not self.dialogs['preferences']:
            dlg = preferences.PreferencesDialog(parent=self)
            self.dialogs['preferences'] = dlg
            self.dialogs['preferences'].CenterOnScreen()

        self.dialogs['preferences'].ShowModal()
        
    def DispHistogram(self, event):
        """
        Init histogram display canvas and tools
        """
        self.histogram = histogram.HistFrame(self,
                                             id=wx.ID_ANY, pos=wx.DefaultPosition, size=(400,300),
                                             style=wx.DEFAULT_FRAME_STYLE)

        #show new display
        self.histogram.Show()
        self.histogram.Refresh()
        self.histogram.Update()

    def DispProfile(self, event):
        """
        Init profile canvas and tools
        """
        self.profile = profile.ProfileFrame(self,
                                           id=wx.ID_ANY, pos=wx.DefaultPosition, size=(400,300),
                                           style=wx.DEFAULT_FRAME_STYLE)
        self.profile.Show()
        self.profile.Refresh()
        self.profile.Update()
        
    def DispMapCalculator(self, event):
        """
        Init map calculator for interactive creation of mapcalc statements
        """
        
        self.mapcalculator = mapcalculator.MapCalcFrame(self, wx.ID_ANY, title='',
                                                        dimension=2)

    def Disp3DMapCalculator(self, event):
        """
        Init map calculator for interactive creation of mapcalc statements
        """
        
        self.mapcalculator = mapcalculator.MapCalcFrame(self, wx.ID_ANY, title='',
                                                        dimension=3)

    def AddToolbarButton(self, toolbar, label, icon, help, handler):
        """!Adds button to the given toolbar"""

        if not label:
            toolbar.AddSeparator()
            return
        tool = toolbar.AddLabelTool(id=wx.ID_ANY, label=label, bitmap=icon, shortHelp=help)
        self.Bind(wx.EVT_TOOL, handler, tool)

    def ToolbarData(self):

        return   (
                 ('newdisplay', Icons["newdisplay"].GetBitmap(),
                  Icons["newdisplay"].GetLabel(), self.OnNewDisplay),
                 ('', '', '', ''),
                 ('workspaceLoad', Icons["workspaceLoad"].GetBitmap(),
                  Icons["workspaceLoad"].GetLabel(), self.OnWorkspace),
                 ('workspaceOpen', Icons["workspaceOpen"].GetBitmap(),
                  Icons["workspaceOpen"].GetLabel(), self.OnWorkspaceOpen),
                 ('workspaceSave', Icons["workspaceSave"].GetBitmap(),
                  Icons["workspaceSave"].GetLabel(), self.OnWorkspaceSave),
                 ('', '', '', ''),
                 ('addrast', Icons["addrast"].GetBitmap(),
                  Icons["addrast"].GetLabel(), self.OnAddRaster),
                 ('addshaded', Icons["addshaded"].GetBitmap(),
                  _("Add various raster-based map layers"), self.OnAddRasterMisc),
                 ('addvect', Icons["addvect"].GetBitmap(),
                  Icons["addvect"].GetLabel(), self.OnAddVector),
                 ('addthematic', Icons["addthematic"].GetBitmap(),
                  _("Add various vector-based map layers"), self.OnAddVectorMisc),
                 ('addcmd',  Icons["addcmd"].GetBitmap(),
                  Icons["addcmd"].GetLabel(),  self.OnAddCommand),
                 ('addgrp',  Icons["addgrp"].GetBitmap(),
                  Icons["addgrp"].GetLabel(), self.OnAddGroup),
                 ('addovl',  Icons["addovl"].GetBitmap(),
                  Icons["addovl"].GetLabel(), self.OnAddOverlay),
                 ('delcmd',  Icons["delcmd"].GetBitmap(),
                  Icons["delcmd"].GetLabel(), self.OnDeleteLayer),
                 ('', '', '', ''),
                 ('attrtable', Icons["attrtable"].GetBitmap(),
                  Icons["attrtable"].GetLabel(), self.OnShowAttributeTable)
                  )

    def OnImportDxfFile(self, event):
        """!Convert multiple DXF layers to GRASS vector map layers"""
        dlg = gdialogs.MultiImportDialog(parent=self, type='dxf',
                                         title=_("Import DXF layers"))
        dlg.ShowModal()

    def OnImportGdalLayers(self, event):
        """!Convert multiple GDAL layers to GRASS raster map layers"""
        dlg = gdialogs.MultiImportDialog(parent=self, type='gdal',
                                         title=_("Import GDAL layers"))
        dlg.ShowModal()

    def OnLinkGdalLayers(self, event):
        """!Link multiple GDAL layers to GRASS raster map layers"""
        dlg = gdialogs.MultiImportDialog(parent=self, type='gdal',
                                         title=_("Link GDAL layers"),
                                         link = True)
        dlg.ShowModal()
        
    def OnImportOgrLayers(self, event):
        """!Convert multiple OGR layers to GRASS vector map layers"""
        dlg = gdialogs.MultiImportDialog(parent=self, type='ogr',
                                         title=_("Import OGR layers"))
        dlg.ShowModal()
    
    def OnLinkOgrLayers(self, event):
        """!Links multiple OGR layers to GRASS vector map layers"""
        dlg = gdialogs.MultiImportDialog(parent=self, type='ogr',
                                         title=_("Link OGR layers"),
                                         link = True)
        dlg.ShowModal()
        
    def OnImportWMS(self, event):
        """!Import data from OGC WMS server"""
        dlg = ogc_services.WMSDialog(parent = self, service = 'wms')
        dlg.CenterOnScreen()
        
        if dlg.ShowModal() == wx.ID_OK: # -> import layers
            layers = dlg.GetLayers()
            
            if len(layers.keys()) > 0:
                for layer in layers.keys():
                    cmd = ['r.in.wms',
                           'mapserver=%s' % dlg.GetSettings()['server'],
                           'layers=%s' % layer,
                           'output=%s' % layer]
                    styles = ','.join(layers[layer])
                    if styles:
                        cmd.append('styles=%s' % styles)
                    self.goutput.RunCmd(cmd, switchPage = True)
            else:
                self.goutput.WriteWarning(_("Nothing to import. No WMS layer selected."))
        
        dlg.Destroy()
        
    def OnShowAttributeTable(self, event):
        """
        Show attribute table of the given vector map layer
        """
        if not self.curr_page:
            self.MsgNoLayerSelected()
            return
        
        layer = self.curr_page.maptree.layer_selected
        # no map layer selected
        if not layer:
            self.MsgNoLayerSelected()
            return
        
        # available only for vector map layers
        try:
            maptype = self.curr_page.maptree.GetPyData(layer)[0]['maplayer'].type
        except:
            maptype = None
        
        if not maptype or maptype != 'vector':
            wx.MessageBox(parent=self,
                          message=_("Attribute management is available only "
                                    "for vector maps."),
                          caption=_("Message"),
                          style=wx.OK | wx.ICON_INFORMATION | wx.CENTRE)
            return
        
        if not self.curr_page.maptree.GetPyData(layer)[0]:
            return
        dcmd = self.curr_page.maptree.GetPyData(layer)[0]['cmd']
        if not dcmd:
            return
        
        busy = wx.BusyInfo(message=_("Please wait, loading attribute data..."),
                           parent=self)
        wx.Yield()
        
        dbmanager = dbm.AttributeManager(parent=self, id=wx.ID_ANY,
                                         size=wx.Size(500, 300),
                                         item=layer, log=self.goutput)
        
        busy.Destroy()
        
        # register ATM dialog
        self.dialogs['atm'].append(dbmanager)
        
        # show ATM window
        dbmanager.Show()
        
    def OnNewDisplay(self, event=None):
        """!Create new layer tree and map display instance"""
        self.NewDisplay()

    def NewDisplay(self, show=True):
        """!Create new layer tree, which will
        create an associated map display frame

        @param show show map display window if True

        @return reference to mapdisplay intance
        """
        Debug.msg(1, "GMFrame.NewDisplay(): idx=%d" % self.disp_idx)
        
        # make a new page in the bookcontrol for the layer tree (on page 0 of the notebook)
        self.pg_panel = wx.Panel(self.gm_cb, id=wx.ID_ANY, style= wx.EXPAND)
        self.gm_cb.AddPage(self.pg_panel, text="Display "+ str(self.disp_idx + 1), select = True)
        self.curr_page = self.gm_cb.GetCurrentPage()
        
        # create layer tree (tree control for managing GIS layers)  and put on new notebook page
        self.curr_page.maptree = wxgui_utils.LayerTree(self.curr_page, id=wx.ID_ANY, pos=wx.DefaultPosition,
                                                       size=wx.DefaultSize, style=wx.TR_HAS_BUTTONS
                                                       |wx.TR_LINES_AT_ROOT|wx.TR_HIDE_ROOT
                                                       |wx.TR_DEFAULT_STYLE|wx.NO_BORDER|wx.FULL_REPAINT_ON_RESIZE,
                                                       idx=self.disp_idx, lmgr=self, notebook=self.gm_cb,
                                                       auimgr=self._auimgr, showMapDisplay=show)
        
        # layout for controls
        cb_boxsizer = wx.BoxSizer(wx.VERTICAL)
        cb_boxsizer.Add(self.curr_page.maptree, proportion=1, flag=wx.EXPAND, border=1)
        self.curr_page.SetSizer(cb_boxsizer)
        cb_boxsizer.Fit(self.curr_page.maptree)
        self.curr_page.Layout()
        self.curr_page.maptree.Layout()
        
        # use default window layout
        if UserSettings.Get(group='general', key='defWindowPos', subkey='enabled') is True:
            dim = UserSettings.Get(group='general', key='defWindowPos', subkey='dim')
            idx = 4 + self.disp_idx * 4
            try:
                x, y = map(int, dim.split(',')[idx:idx + 2])
                w, h = map(int, dim.split(',')[idx + 2:idx + 4])
                self.curr_page.maptree.mapdisplay.SetPosition((x, y))
                self.curr_page.maptree.mapdisplay.SetSize((w, h))
            except:
                pass
        
        self.disp_idx += 1
        
        return self.curr_page.maptree.mapdisplay

    # toolBar button handlers
    def OnAddRaster(self, event):
        """!Add raster map layer"""
        # start new map display if no display is available
        if not self.curr_page:
            self.NewDisplay(show=False)
        
        self.AddRaster(event)
        
    def OnAddRasterMisc(self, event):
        """!Add raster menu"""
        # start new map display if no display is available
        if not self.curr_page:
            self.NewDisplay(show=False)

        point = wx.GetMousePosition()
        rastmenu = wx.Menu()

        # add items to the menu
        if self.curr_page.maptree.mapdisplay.toolbars['nviz']:
            addrast3d = wx.MenuItem(rastmenu, -1, Icons ["addrast3d"].GetLabel())
            addrast3d.SetBitmap(Icons["addrast3d"].GetBitmap (self.iconsize))
            rastmenu.AppendItem(addrast3d)
            self.Bind(wx.EVT_MENU, self.AddRaster3d, addrast3d)

        addshaded = wx.MenuItem(rastmenu, -1, Icons ["addshaded"].GetLabel())
        addshaded.SetBitmap(Icons["addshaded"].GetBitmap (self.iconsize))
        rastmenu.AppendItem(addshaded)
        self.Bind(wx.EVT_MENU, self.AddShaded, addshaded)

        addrgb = wx.MenuItem(rastmenu, -1, Icons["addrgb"].GetLabel())
        addrgb.SetBitmap(Icons["addrgb"].GetBitmap(self.iconsize))
        rastmenu.AppendItem(addrgb)
        self.Bind(wx.EVT_MENU, self.AddRGB, addrgb)

        addhis = wx.MenuItem(rastmenu, -1, Icons ["addhis"].GetLabel())
        addhis.SetBitmap(Icons["addhis"].GetBitmap (self.iconsize))
        rastmenu.AppendItem(addhis)
        self.Bind(wx.EVT_MENU, self.AddHIS, addhis)

        addrastarrow = wx.MenuItem(rastmenu, -1, Icons ["addrarrow"].GetLabel())
        addrastarrow.SetBitmap(Icons["addrarrow"].GetBitmap (self.iconsize))
        rastmenu.AppendItem(addrastarrow)
        self.Bind(wx.EVT_MENU, self.AddRastarrow, addrastarrow)

        addrastnums = wx.MenuItem(rastmenu, -1, Icons ["addrnum"].GetLabel())
        addrastnums.SetBitmap(Icons["addrnum"].GetBitmap (self.iconsize))
        rastmenu.AppendItem(addrastnums)
        self.Bind(wx.EVT_MENU, self.AddRastnum, addrastnums)

        # Popup the menu.  If an item is selected then its handler
        # will be called before PopupMenu returns.
        self.PopupMenu(rastmenu)
        rastmenu.Destroy()
        
        # show map display
        self.curr_page.maptree.mapdisplay.Show()

    def OnAddVector(self, event):
        """!Add vector map layer"""
        # start new map display if no display is available
        if not self.curr_page:
            self.NewDisplay(show=False)
        
        self.AddVector(event)
        
    def OnAddVectorMisc(self, event):
        """!Add vector menu"""
        # start new map display if no display is available
        if not self.curr_page:
            self.NewDisplay(show=False)

        point = wx.GetMousePosition()
        vectmenu = wx.Menu()
        
        addtheme = wx.MenuItem(vectmenu, -1, Icons["addthematic"].GetLabel())
        addtheme.SetBitmap(Icons["addthematic"].GetBitmap(self.iconsize))
        vectmenu.AppendItem(addtheme)
        self.Bind(wx.EVT_MENU, self.AddThemeMap, addtheme)

        addchart = wx.MenuItem(vectmenu, -1, Icons["addchart"].GetLabel())
        addchart.SetBitmap(Icons["addchart"].GetBitmap(self.iconsize))
        vectmenu.AppendItem(addchart)
        self.Bind(wx.EVT_MENU, self.AddThemeChart, addchart)

        # Popup the menu.  If an item is selected then its handler
        # will be called before PopupMenu returns.
        self.PopupMenu(vectmenu)
        vectmenu.Destroy()

        # show map display
        self.curr_page.maptree.mapdisplay.Show()

    def OnAddOverlay(self, event):
        """!Add decoration overlay menu""" 
        # start new map display if no display is available
        if not self.curr_page:
            self.NewDisplay(show=False)

        point = wx.GetMousePosition()
        ovlmenu = wx.Menu()

        addgrid = wx.MenuItem(ovlmenu, wx.ID_ANY, Icons["addgrid"].GetLabel())
        addgrid.SetBitmap(Icons["addgrid"].GetBitmap(self.iconsize))
        ovlmenu.AppendItem(addgrid)
        self.Bind(wx.EVT_MENU, self.AddGrid, addgrid)
        
        addlabels = wx.MenuItem(ovlmenu, wx.ID_ANY, Icons["addlabels"].GetLabel())
        addlabels.SetBitmap(Icons["addlabels"].GetBitmap(self.iconsize))
        ovlmenu.AppendItem(addlabels)
        self.Bind(wx.EVT_MENU, self.OnAddLabels, addlabels)
        
        addgeodesic = wx.MenuItem(ovlmenu, wx.ID_ANY, Icons["addgeodesic"].GetLabel())
        addgeodesic.SetBitmap(Icons["addgeodesic"].GetBitmap(self.iconsize))
        ovlmenu.AppendItem(addgeodesic)
        self.Bind(wx.EVT_MENU, self.AddGeodesic, addgeodesic)
        
        addrhumb = wx.MenuItem(ovlmenu, wx.ID_ANY, Icons["addrhumb"].GetLabel())
        addrhumb.SetBitmap(Icons["addrhumb"].GetBitmap(self.iconsize))
        ovlmenu.AppendItem(addrhumb)
        self.Bind(wx.EVT_MENU, self.AddRhumb, addrhumb)

        # Popup the menu.  If an item is selected then its handler
        # will be called before PopupMenu returns.
        self.PopupMenu(ovlmenu)
        ovlmenu.Destroy()

        # show map display
        self.curr_page.maptree.mapdisplay.Show()

    def AddRaster(self, event):
        self.notebook.SetSelection(0)
        self.curr_page.maptree.AddLayer('raster')

    def AddRaster3d(self, event):
        self.notebook.SetSelection(0)
        self.curr_page.maptree.AddLayer('3d-raster')

    def AddRGB(self, event):
        """!Add RGB layer"""
        self.notebook.SetSelection(0)
        self.curr_page.maptree.AddLayer('rgb')

    def AddHIS(self, event):
        """!Add HIS layer"""
        self.notebook.SetSelection(0)
        self.curr_page.maptree.AddLayer('his')

    def AddShaded(self, event):
        """!Add shaded relief map layer"""
        self.notebook.SetSelection(0)
        self.curr_page.maptree.AddLayer('shaded')

    def AddRastarrow(self, event):
        """!Add raster flow arrows map"""
        self.notebook.SetSelection(0)
        self.curr_page.maptree.AddLayer('rastarrow')

    def AddRastnum(self, event):
        """!Add raster map with cell numbers"""
        self.notebook.SetSelection(0)
        self.curr_page.maptree.AddLayer('rastnum')

    def AddVector(self, event):
        """!Add vector layer"""
        self.notebook.SetSelection(0)
        self.curr_page.maptree.AddLayer('vector')

    def AddThemeMap(self, event):
        """!Add thematic map layer"""
        self.notebook.SetSelection(0)
        self.curr_page.maptree.AddLayer('thememap')

    def AddThemeChart(self, event):
        """!Add thematic chart layer"""
        self.notebook.SetSelection(0)
        self.curr_page.maptree.AddLayer('themechart')

    def OnAddCommand(self, event):
        """!Add command line layer"""
        # start new map display if no display is available
        if not self.curr_page:
            self.NewDisplay(show=False)

        self.notebook.SetSelection(0)
        self.curr_page.maptree.AddLayer('command')

        # show map display
        self.curr_page.maptree.mapdisplay.Show()

    def OnAddGroup(self, event):
        """!Add layer group"""
        # start new map display if no display is available
        if not self.curr_page:
            self.NewDisplay(show=False)

        self.notebook.SetSelection(0)
        self.curr_page.maptree.AddLayer('group')

        # show map display
        self.curr_page.maptree.mapdisplay.Show()

    def AddGrid(self, event):
        """!Add layer grid"""
        self.notebook.SetSelection(0)
        self.curr_page.maptree.AddLayer('grid')

    def AddGeodesic(self, event):
        """!Add layer geodesic"""
        self.notebook.SetSelection(0)
        self.curr_page.maptree.AddLayer('geodesic')

    def AddRhumb(self, event):
        """!Add layer rhumb"""
        self.notebook.SetSelection(0)
        self.curr_page.maptree.AddLayer('rhumb')

    def OnAddLabels(self, event):
        """!Add layer vector labels"""
        # start new map display if no display is available
        if not self.curr_page:
            self.NewDisplay(show=False)

        self.notebook.SetSelection(0)
        self.curr_page.maptree.AddLayer('labels')

        # show map display
        self.curr_page.maptree.mapdisplay.Show()

    def OnDeleteLayer(self, event):
        """
        Delete selected map display layer in GIS Manager tree widget
        """
        if not self.curr_page or not self.curr_page.maptree.layer_selected:
            self.MsgNoLayerSelected()
            return

        if UserSettings.Get(group='manager', key='askOnRemoveLayer', subkey='enabled'):
            layerName = ''
            for item in self.curr_page.maptree.GetSelections():
                name = str(self.curr_page.maptree.GetItemText(item))
                idx = name.find('(opacity')
                if idx > -1:
                    layerName += '<' + name[:idx].strip(' ') + '>,\n'
                else:
                    layerName += '<' + name + '>,\n'
            layerName = layerName.rstrip(',\n')
            
            if len(layerName) > 2: # <>
                message = _("Do you want to remove map layer(s)\n%s\n"
                            "from layer tree?") % layerName
            else:
                message = _("Do you want to remove selected map layer(s) "
                            "from layer tree?")

            dlg = wx.MessageDialog (parent=self, message=message,
                                    caption=_("Remove map layer"),
                                    style=wx.YES_NO | wx.YES_DEFAULT | wx.CANCEL | wx.ICON_QUESTION)

            if dlg.ShowModal() in [wx.ID_NO, wx.ID_CANCEL]:
                dlg.Destroy()
                return

            dlg.Destroy()

        for layer in self.curr_page.maptree.GetSelections():
            if self.curr_page.maptree.GetPyData(layer)[0]['type'] == 'group':
                self.curr_page.maptree.DeleteChildren(layer)
            self.curr_page.maptree.Delete(layer)
        
    def OnKeyDown(self, event):
        """!Key pressed"""
        kc = event.GetKeyCode()
        
        if event.ControlDown():
            if kc == wx.WXK_TAB:
                # switch layer list / command output
                if self.notebook.GetSelection() == 0:
                    self.notebook.SetSelection(1)
                else:
                    self.notebook.SetSelection(0)
        
        try:
            ckc = chr(kc)
        except ValueError:
            event.Skip()
            return
        
        if event.CtrlDown():
            if kc == 'R':
                self.OnAddRaster(None)
            elif kc == 'V':
                self.OnAddVector(None)
        
        event.Skip()

    def OnQuit(self, event):
        """!Quit GRASS session (wxGUI and shell)"""
        # quit wxGUI session
        self.OnCloseWindow(event)

        # quit GRASS shell
        try:
            pid = int(os.environ['GIS_LOCK'])
        except (KeyError, ValueError):
            sys.stderr.write('\n')
            sys.stderr.write(_("WARNING: Unable to quit GRASS, uknown GIS_LOCK"))
            return
        
        os.kill(pid, signal.SIGQUIT)
        
    def OnCloseWindow(self, event):
        """!Cleanup when wxGUI is quit"""
        if not self.curr_page:
            self._auimgr.UnInit()
            self.Destroy()
            return
        
        maptree = self.curr_page.maptree
        if UserSettings.Get(group='manager', key='askOnQuit', subkey='enabled'):
            if self.workspaceFile:
                message = _("Do you want to save changes in the workspace?")
            else:
                message = _("Do you want to store current settings "
                            "to workspace file?")
            
            # ask user to save current settings
            if maptree.GetCount() > 0:
                dlg = wx.MessageDialog(self,
                                       message=message,
                                       caption=_("Quit GRASS GUI"),
                                       style=wx.YES_NO | wx.YES_DEFAULT |
                                       wx.CANCEL | wx.ICON_QUESTION | wx.CENTRE)
                ret = dlg.ShowModal()
                if ret == wx.ID_YES:
                    if not self.workspaceFile:
                        self.OnWorkspaceSaveAs()
                    else:
                        self.SaveToWorkspaceFile(self.workspaceFile)
                elif ret == wx.ID_CANCEL:
                    event.Veto()
                    dlg.Destroy()
                    return
                dlg.Destroy()
        
        # don't ask any more...
        UserSettings.Set(group = 'manager', key = 'askOnQuit', subkey = 'enabled',
                         value = False)

        for page in range(self.gm_cb.GetPageCount()):
            self.gm_cb.GetPage(0).maptree.mapdisplay.OnCloseWindow(event)

        self.gm_cb.DeleteAllPages()
        
        self._auimgr.UnInit()
        self.Destroy()
        
    def MsgNoLayerSelected(self):
        """!Show dialog message 'No layer selected'"""
        wx.MessageBox(parent=self,
                      message=_("No map layer selected. Operation cancelled."),
                      caption=_("Message"),
                      style=wx.OK | wx.ICON_INFORMATION | wx.CENTRE)
    
class GMApp(wx.App):
    def __init__(self, workspace = None):
        """!Main GUI class.

        @param workspace path to the workspace file
        """
        self.workspaceFile = workspace
        
        # call parent class initializer
        wx.App.__init__(self, False)
        
        self.locale = wx.Locale(language = wx.LANGUAGE_DEFAULT)
        
    def OnInit(self):
        """!Initialize all available image handlers

        @return True
        """
        wx.InitAllImageHandlers()

        # create splash screen
        introImagePath = os.path.join(globalvar.ETCWXDIR, "images", "grass_splash.png")
        introImage     = wx.Image(introImagePath, wx.BITMAP_TYPE_PNG)
        introBmp       = introImage.ConvertToBitmap()
        wx.SplashScreen (bitmap=introBmp, splashStyle=wx.SPLASH_CENTRE_ON_SCREEN | wx.SPLASH_TIMEOUT,
                         milliseconds=2000, parent=None, id=wx.ID_ANY)
        wx.Yield()
        
        # create and show main frame
        mainframe = GMFrame(parent=None, id=wx.ID_ANY,
                            workspace = self.workspaceFile)

        mainframe.Show()
        self.SetTopWindow(mainframe)

        return True

class Usage(Exception):
    def __init__(self, msg):
        self.msg = msg

def printHelp():
    """!Print program help"""
    print >> sys.stderr, "Usage:"
    print >> sys.stderr, " python wxgui.py [options]"
    print >> sys.stderr, "%sOptions:" % os.linesep
    print >> sys.stderr, " -w\t--workspace file\tWorkspace file to load"
    sys.exit(0)

def process_opt(opts, args):
    """!Process command-line arguments"""
    workspaceFile = None
    for o, a in opts:
        if o in ("-h", "--help"):
            printHelp()
            
        if o in ("-w", "--workspace"):
            if a != '':
                workspaceFile = str(a)
            else:
                workspaceFile = args.pop(0)

    return (workspaceFile,)

def main(argv=None):
    #
    # process command-line arguments
    #
    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, args = getopt.getopt(argv[1:], "hw:",
                                       ["help", "workspace"])
        except getopt.error, msg:
            raise Usage(msg)

    except Usage, err:
        print >> sys.stderr, err.msg
        print >> sys.stderr, "for help use --help"
        printHelp()

    workspaceFile = process_opt(opts, args)[0]

    #
    # run application
    #
    app = GMApp(workspaceFile)
    # suppress wxPython logs
    q = wx.LogNull()

    app.MainLoop()

if __name__ == "__main__":
    sys.exit(main())
