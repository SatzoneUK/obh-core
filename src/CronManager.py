# for localized messages
from . import _

from Components.ActionMap import ActionMap
from Components.About import about
from Components.config import getConfigListEntry, config, ConfigText, ConfigSelection, ConfigInteger, ConfigClock, NoSave, configfile
from Components.ConfigList import ConfigListScreen
from Components.Console import Console
from Components.Label import Label
from Components.Sources.List import List
from Components.Pixmap import Pixmap
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Tools.Directories import fileExists
from os import system, listdir, rename, path, mkdir
from time import sleep

config.vixsettings.cronmanager_commandtype = NoSave(ConfigSelection(choices = [ ('custom',_("Custom")),('predefined',_("Predefined")) ]))
config.vixsettings.cronmanager_cmdtime = NoSave(ConfigClock(default=0))
config.vixsettings.cronmanager_cmdtime.value, mytmpt = ([0, 0], [0, 0])
config.vixsettings.cronmanager_user_command = NoSave(ConfigText(fixed_size=False))
config.vixsettings.cronmanager_runwhen = NoSave(ConfigSelection(default='Daily', choices = [('Hourly', _("Hourly")),('Daily', _("Daily")),('Weekly', _("Weekly")),('Monthly', _("Monthly"))]))
config.vixsettings.cronmanager_dayofweek = NoSave(ConfigSelection(default='Monday', choices = [('Monday', _("Monday")),('Tuesday', _("Tuesday")),('Wednesday', _("Wednesday")),('Thursday', _("Thursday")),('Friday', _("Friday")),('Saturday', _("Saturday")),('Sunday', _("Sunday"))]))
config.vixsettings.cronmanager_dayofmonth = NoSave(ConfigInteger(default=1, limits=(1, 31)))

class VIXCronManager(Screen):
	skin = """
		<screen position="center,center" size="590,400" title="Cron Manager">
			<widget name="lab1" position="10,0" size="100,24" font="Regular;20" valign="center" transparent="0" />
			<widget name="labdisabled" position="110,0" size="100,24" font="Regular;20" valign="center" halign="center" backgroundColor="red" zPosition="1" />
			<widget name="labactive" position="110,0" size="100,24" font="Regular;20" valign="center" halign="center" backgroundColor="green" zPosition="2" />
			<widget name="lab2" position="240,0" size="150,24" font="Regular;20" valign="center" transparent="0" />
			<widget name="labstop" position="390,0" size="100,24" font="Regular;20" valign="center" halign="center" backgroundColor="red" zPosition="1" />
			<widget name="labrun" position="390,0" size="100,24" font="Regular;20" valign="center" halign="center" backgroundColor="green" zPosition="2"/>
			<widget source="list" render="Listbox" position="10,35" size="540,325" scrollbarMode="showOnDemand" >
				<convert type="StringList" />
			</widget>
			<ePixmap pixmap="skin_default/buttons/red.png" position="0,350" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/yellow.png" position="150,350" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="300,350" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/blue.png" position="450,350" size="140,40" alphatest="on" />
			<widget name="key_red" position="0,350" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
			<widget name="key_yellow" position="150,350" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1" />
			<widget name="key_green" position="300,350" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1" />
			<widget name="key_blue" position="450,350" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1" />
		</screen>"""


	def __init__(self, session):
		Screen.__init__(self, session)
		if not path.exists('/usr/scripts'):
			mkdir('/usr/scripts', 0755)
		Screen.setTitle(self, _("Cron Manager"))
		self.onChangedEntry = [ ]
		self['lab1'] = Label(_("Autostart:"))
		self['labactive'] = Label(_(_("Active")))
		self['labdisabled'] = Label(_(_("Disabled")))
		self['lab2'] = Label(_("Current Status:"))
		self['labstop'] = Label(_("Stopped"))
		self['labrun'] = Label(_("Running"))
		self['labrun'].hide()
		self['labactive'].hide()
		self.summary_running = ''
		self['key'] = Label(_("H: = Hourly / D: = Daily / W: = Weekly / M: = Monthly"))
		self.Console = Console()
		self.my_crond_active = False
		self.my_crond_run = False

		self['key_red'] = Label(_("Delete"))
		self['key_green'] = Label(_("Add"))
		self['key_yellow'] = Label(_("Start"))
		self['key_blue'] = Label(_("Autostart"))
		self.list = []
		self['list'] = List(self.list)
		self['actions'] = ActionMap(['WizardActions', 'ColorActions', "MenuActions"], {'ok': self.info, 'back': self.UninstallCheck, 'red': self.delcron, 'green': self.addtocron, 'yellow': self.CrondStart, 'blue': self.autostart, "menu": self.closeRecursive})
		if not self.selectionChanged in self["list"].onSelectionChanged:
			self["list"].onSelectionChanged.append(self.selectionChanged)
		self.service_name = 'busybox-cron'
		self.InstallCheck()

	def InstallCheck(self):
		self.Console.ePopen('/usr/bin/opkg list_installed ' + self.service_name, self.checkNetworkState)

	def checkNetworkState(self, str, retval, extra_args):
		if not str:
			self.feedscheck = self.session.open(MessageBox,_('Please wait whilst feeds state is checked.'), MessageBox.TYPE_INFO, enable_input = False)
			self.feedscheck.setTitle(_('Checking Feeds'))
			cmd1 = "opkg update"
			self.CheckConsole = Console()
			self.CheckConsole.ePopen(cmd1, self.checkNetworkStateFinished)
		else:
			self.updateList()

	def checkNetworkStateFinished(self, result, retval,extra_args=None):
		if (float(about.getImageVersionString()) < 3.0 and result.find('mipsel/Packages.gz, wget returned 1') != -1) or (float(about.getImageVersionString()) >= 3.0 and result.find('mips32el/Packages.gz, wget returned 1') != -1):
			self.session.openWithCallback(self.InstallPackageFailed, MessageBox, _("Sorry feeds are down for maintenance, please try again later."), type=MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)
		elif result.find('bad address') != -1:
			self.session.openWithCallback(self.InstallPackageFailed, MessageBox, _("Your STB_BOX is not connected to the internet, please check your network settings and try again."), type=MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)
		else:
			self.session.openWithCallback(self.InstallPackage, MessageBox, _('Ready to install "%s" ?') % self.service_name, MessageBox.TYPE_YESNO)

	def InstallPackage(self, val):
		if val:
			self.doInstall(self.installComplete, self.service_name)
		else:
			self.feedscheck.close()
			self.close()

	def InstallPackageFailed(self, val):
		self.feedscheck.close()
		self.close()

	def doInstall(self, callback, pkgname):
		self.message = self.session.open(MessageBox,_("please wait..."), MessageBox.TYPE_INFO, enable_input = False)
		self.message.setTitle(_('Installing Service'))
		self.Console.ePopen('/usr/bin/opkg install ' + pkgname, callback)

	def installComplete(self,result = None, retval = None, extra_args = None):
		self.message.close()
		self.feedscheck.close()
		self.updateList()

	def UninstallCheck(self):
		if self.my_crond_run == False:
			self.Console.ePopen('/usr/bin/opkg list_installed ' + self.service_name, self.RemovedataAvail)
		else:
			self.close()

	def RemovedataAvail(self, str, retval, extra_args):
		if str:
			self.session.openWithCallback(self.RemovePackage, MessageBox, _('Ready to remove "%s" ?') % self.service_name)
		else:
			self.close()

	def RemovePackage(self, val):
		if val:
			self.doRemove(self.removeComplete, self.service_name)
		else:
			self.close()

	def doRemove(self, callback, pkgname):
		self.message = self.session.open(MessageBox,_("please wait..."), MessageBox.TYPE_INFO, enable_input = False)
		self.message.setTitle(_('Removing Service'))
		self.Console.ePopen('/usr/bin/opkg remove ' + pkgname + ' --force-remove --autoremove', callback)

	def removeComplete(self,result = None, retval = None, extra_args = None):
		self.message.close()
		self.close()

	def createSummary(self):
		from Screens.PluginBrowser import PluginBrowserSummary
		return PluginBrowserSummary

	def selectionChanged(self):
		try:
			if self["list"].getCurrent():
				name = str(self["list"].getCurrent()[0])
			else:
				name = ""
		except:
				name = ""
		desc = _("Current Status:") + ' ' +self.summary_running
		for cb in self.onChangedEntry:
			cb(name, desc)

	def CrondStart(self):
		if self.my_crond_run == False:
			self.Console.ePopen('/etc/init.d/busybox-cron start')
			sleep(3)
			self.updateList()
		elif self.my_crond_run == True:
			self.Console.ePopen('/etc/init.d/busybox-cron stop')
			sleep(3)
			self.updateList()

	def autostart(self):
		if fileExists('/etc/rc2.d/S20busybox-cron'):
			self.Console.ePopen('update-rc.d -f busybox-cron remove')
		else:
			self.Console.ePopen('update-rc.d -f busybox-cron defaults')
		sleep(3)
		self.updateList()

	def addtocron(self):
		self.session.openWithCallback(self.updateList, VIXSetupCronConf)

	def updateList(self,result = None, retval = None, extra_args = None):
		import process
		p = process.ProcessList()
		crond_process = str(p.named('crond')).strip('[]')
		self['labrun'].hide()
		self['labstop'].hide()
		self['labactive'].hide()
		self['labdisabled'].hide()
		self.my_crond_active = False
		self.my_crond_run = False
		if path.exists('/etc/rc3.d/S20busybox-cron'):
			self['labdisabled'].hide()
			self['labactive'].show()
			self.my_crond_active = True
		else:
			self['labactive'].hide()
			self['labdisabled'].show()
		if crond_process:
			self.my_crond_run = True
		if self.my_crond_run == True:
			self['labstop'].hide()
			self['labrun'].show()
			self['key_yellow'].setText(_("Stop"))
			self.summary_running = _("Running")
		else:
			self['labstop'].show()
			self['labrun'].hide()
			self['key_yellow'].setText(_("Start"))
			self.summary_running = _("Stopped")

		self.list = []
		if path.exists('/etc/cron/crontabs/root'):
			f = open('/etc/cron/crontabs/root', 'r')
			for line in f.readlines():
				parts = line.strip().split()
				if parts:
					if parts[1] == '*':
						try:
							line2 = 'H: 00:' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7] + parts[8] + parts[9]
						except:
							try:
								line2 = 'H: 00:' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7] + parts[8]
							except:
								try:
									line2 = 'H: 00:' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7]
								except:
									try:
										line2 = 'H: 00:' + parts[0].zfill(2) + '\t' + parts[5] + parts[6]
									except:
										line2 = 'H: 00:' + parts[0].zfill(2) + '\t' + parts[5]
						res = (line2, line)
						self.list.append(res)
					elif parts[2] == '*' and parts[4] == '*':
						try:
							line2 = 'D: ' + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7] + parts[8] + parts[9]
						except:
							try:
								line2 = 'D: ' + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7] + parts[8]
							except:
								try:
									line2 = 'D: ' + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7]
								except:
									try:
										line2 = 'D: ' + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6]
									except:
										line2 = 'D: ' + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5]
						res = (line2, line)
						self.list.append(res)
					elif parts[3] == '*':
						if parts[4] == "*":
							try:
								line2 = 'M:  Day ' + parts[2] + '  ' + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7] + parts[8] + parts[9]
							except:
								try:
									line2 = 'M:  Day ' + parts[2] + '  ' + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7] + parts[8]
								except:
									try:
										line2 = 'M:  Day ' + parts[2] + '  ' + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7]
									except:
										try:
											line2 = 'M:  Day ' + parts[2] + '  ' + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6]
										except:
											line2 = 'M:  Day ' + parts[2] + '  ' + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5]
						header = 'W:  '
						day = ""
						if str(parts[4]).find('0') >= 0:
							day = 'Sun '
						if str(parts[4]).find('1') >= 0:
							day += 'Mon '
						if str(parts[4]).find('2') >= 0:
							day += 'Tues '
						if str(parts[4]).find('3') >= 0:
							day += 'Wed '
						if str(parts[4]).find('4') >= 0:
							day += 'Thurs '
						if str(parts[4]).find('5') >= 0:
							day += 'Fri '
						if str(parts[4]).find('6') >= 0:
							day += 'Sat '

						if day:
							try:
								line2 = header + day + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7] + parts[8] + parts[9]
							except:
								try:
									line2 = header + day + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7] + parts[8]
								except:
									try:
										line2 = header + day + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7]
									except:
										try:
											line2 = header + day + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6]
										except:
											line2 = header + day + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5]
						res = (line2, line)
						self.list.append(res)
			f.close()
		self['list'].list = self.list
		self["actions"].setEnabled(True)

	def delcron(self):
		self.sel = self['list'].getCurrent()
		if self.sel:
			parts = self.sel[0]
			parts = parts.split('\t')
			message = _("Are you sure you want to delete this:\n ") + parts[1]
			ybox = self.session.openWithCallback(self.doDelCron, MessageBox, message, MessageBox.TYPE_YESNO)
			ybox.setTitle(_("Remove Confirmation"))

	def doDelCron(self, answer):
		if answer:
			mysel = self['list'].getCurrent()
			if mysel:
				myline = mysel[1]
				file('/etc/cron/crontabs/root.tmp', 'w').writelines([l for l in file('/etc/cron/crontabs/root').readlines() if myline not in l])
				rename('/etc/cron/crontabs/root.tmp','/etc/cron/crontabs/root')
				rc = system('crontab /etc/cron/crontabs/root -c /etc/cron/crontabs')
				self.updateList()

	def info(self):
		mysel = self['list'].getCurrent()
		if mysel:
			myline = mysel[1]
			self.session.open(MessageBox, _(myline), MessageBox.TYPE_INFO)

	def closeRecursive(self):
		self.close(True)

class VIXSetupCronConf(Screen, ConfigListScreen):
	skin = """
		<screen position="center,center" size="560,400" title="Cron Manager">
			<widget name="config" position="10,20" size="540,400" scrollbarMode="showOnDemand" />
			<ePixmap pixmap="skin_default/buttons/red.png" position="90,350" size="140,40" alphatest="on" />
			<widget name="key_red" position="90,350" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
			<widget name="HelpWindow" pixmap="skin_default/vkey_icon.png" position="160,260" zPosition="1" size="1,1" transparent="1" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/key_text.png" position="250,353" zPosition="4" size="35,25" alphatest="on" transparent="1" />
		</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("Cron Manager"))
		self.onChangedEntry = [ ]
		self.list = []
		ConfigListScreen.__init__(self, self.list, session = self.session, on_change = self.changedEntry)
		self['key_red'] = Label(_("Save"))
		self['actions'] = ActionMap(['WizardActions', 'ColorActions', 'VirtualKeyboardActions', "MenuActions"], {'red': self.checkentry, 'back': self.close, 'showVirtualKeyboard': self.KeyText, "menu": self.closeRecursive})
		self["HelpWindow"] = Pixmap()
		self["HelpWindow"].hide()
		self.createSetup()

	def createSetup(self):
		predefinedlist = []
		f = listdir('/usr/scripts')
		if f:
			for line in f:
				parts = line.split()
				path = "/usr/scripts/"
				pkg = parts[0]
				description = path + parts[0]
				if pkg.find('.sh') >= 0:
					predefinedlist.append((description, pkg))
			predefinedlist.sort()
		config.vixsettings.cronmanager_predefined_command = NoSave(ConfigSelection(choices = predefinedlist))
		self.editListEntry = None
		self.list = []
		self.list.append(getConfigListEntry(_("Run how often ?"), config.vixsettings.cronmanager_runwhen))
		if config.vixsettings.cronmanager_runwhen.value != 'Hourly':
			self.list.append(getConfigListEntry(_("Time to execute command or script"), config.vixsettings.cronmanager_cmdtime))
		if config.vixsettings.cronmanager_runwhen.value == 'Weekly':
			self.list.append(getConfigListEntry(_("What Day of week ?"), config.vixsettings.cronmanager_dayofweek))
		if config.vixsettings.cronmanager_runwhen.value == 'Monthly':
			self.list.append(getConfigListEntry(_("What Day of month ?"), config.vixsettings.cronmanager_dayofmonth))
		self.list.append(getConfigListEntry(_("Command type"), config.vixsettings.cronmanager_commandtype))
		if config.vixsettings.cronmanager_commandtype.value == 'custom':
			self.list.append(getConfigListEntry(_("Command To Run"), config.vixsettings.cronmanager_user_command))
		else:
			self.list.append(getConfigListEntry(_("Command To Run"), config.vixsettings.cronmanager_predefined_command))
		self["config"].list = self.list
		self["config"].setList(self.list)

	# for summary:
	def changedEntry(self):
		if self["config"].getCurrent()[0] == _("Run how often ?") or self["config"].getCurrent()[0] == _("Command type"):
			self.createSetup()
		for x in self.onChangedEntry:
			x()

	def getCurrentEntry(self):
		return self["config"].getCurrent()[0]

	def KeyText(self):
		sel = self['config'].getCurrent()
		if sel:
			self.vkvar = sel[0]
			if self.vkvar == _("Command To Run"):
				from Screens.VirtualKeyBoard import VirtualKeyBoard
				self.session.openWithCallback(self.VirtualKeyBoardCallback, VirtualKeyBoard, title = self["config"].getCurrent()[0], text = self["config"].getCurrent()[1].getValue())

	def VirtualKeyBoardCallback(self, callback = None):
		if callback is not None and len(callback):
			self["config"].getCurrent()[1].setValue(callback)
			self["config"].invalidate(self["config"].getCurrent())

	def checkentry(self):
		msg = ''
		if (config.vixsettings.cronmanager_commandtype.value == 'predefined' and config.vixsettings.cronmanager_predefined_command.value == '') or config.vixsettings.cronmanager_commandtype.value == 'custom' and config.vixsettings.cronmanager_user_command.value == '':
			msg = 'You must set at least one Command'
		if msg:
			self.session.open(MessageBox, msg, MessageBox.TYPE_ERROR)
		else:
			self.saveMycron()

	def saveMycron(self):
		hour = '%02d' % config.vixsettings.cronmanager_cmdtime.value[0]
		minutes = '%02d' % config.vixsettings.cronmanager_cmdtime.value[1]
		if config.vixsettings.cronmanager_commandtype.value == 'predefined' and config.vixsettings.cronmanager_predefined_command.value != '':
			command = config.vixsettings.cronmanager_predefined_command.value
		else:
			command = config.vixsettings.cronmanager_user_command.value

		if config.vixsettings.cronmanager_runwhen.value == 'Hourly':
			newcron = minutes + ' ' + ' * * * * ' + command.strip() + '\n'
		elif config.vixsettings.cronmanager_runwhen.value == 'Daily':
			newcron = minutes + ' ' + hour + ' * * * ' + command.strip() + '\n'
		elif config.vixsettings.cronmanager_runwhen.value == 'Weekly':
			if config.vixsettings.cronmanager_dayofweek.value == 'Sunday':
				newcron = minutes + ' ' + hour + ' * * 0 ' + command.strip() + '\n'
			elif config.vixsettings.cronmanager_dayofweek.value == 'Monday':
				newcron = minutes + ' ' + hour + ' * * 1 ' + command.strip() + '\n'
			elif config.vixsettings.cronmanager_dayofweek.value == 'Tuesday':
				newcron = minutes + ' ' + hour + ' * * 2 ' + command.strip() + '\n'
			elif config.vixsettings.cronmanager_dayofweek.value == 'Wednesday':
				newcron = minutes + ' ' + hour + ' * * 3 ' + command.strip() + '\n'
			elif config.vixsettings.cronmanager_dayofweek.value == 'Thursday':
				newcron = minutes + ' ' + hour + ' * * 4 ' + command.strip() + '\n'
			elif config.vixsettings.cronmanager_dayofweek.value == 'Friday':
				newcron = minutes + ' ' + hour + ' * * 5 ' + command.strip() + '\n'
			elif config.vixsettings.cronmanager_dayofweek.value == 'Saturday':
				newcron = minutes + ' ' + hour + ' * * 6 ' + command.strip() + '\n'
		elif config.vixsettings.cronmanager_runwhen.value == 'Monthly':
			newcron = minutes + ' ' + hour + ' ' + str(config.vixsettings.cronmanager_dayofmonth.value) + ' * * ' + command.strip() + '\n'
		else:
			command = config.vixsettings.cronmanager_user_command.value

		out = open('/etc/cron/crontabs/root', 'a')
		out.write(newcron)
		out.close()
		rc = system('crontab /etc/cron/crontabs/root -c /etc/cron/crontabs')
		config.vixsettings.cronmanager_predefined_command.value = 'None'
		config.vixsettings.cronmanager_user_command.value = 'None'
		config.vixsettings.cronmanager_runwhen.value = 'Daily'
		config.vixsettings.cronmanager_dayofweek.value = 'Monday'
		config.vixsettings.cronmanager_dayofmonth.value = 1
		config.vixsettings.cronmanager_cmdtime.value, mytmpt = ([0, 0], [0, 0])
		self.close()
