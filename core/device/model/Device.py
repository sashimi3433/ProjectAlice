import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Union, Optional

from core.base.model.ProjectAliceObject import ProjectAliceObject
from core.commons import constants
from core.device.model.DeviceAbility import DeviceAbility
from core.device.model.DeviceException import DeviceTypeUndefined
from core.device.model.DeviceType import DeviceType
from core.myHome.model.Location import Location


class Device(ProjectAliceObject):

	def __init__(self, data: Union[sqlite3.Row, Dict]):

		# settings: Holds the device display settings, such as x and y position, size and that stuff
		# deviceParams: Holds the device non declared params, such as sound muted and so on. These are not controlled values that can be completly random
		# deviceConfigs: Holds the device configurations, provided by the device's .config.template. These configs and values are controlled and cannot be random at all!
		super().__init__()

		if isinstance(data, sqlite3.Row):
			data = self.Commons.dictFromRow(data)

		self._data: dict = data
		self._id: int = data.get('id', -1)
		self._uid: str = data.get('uid', '')
		self._typeName: str = data.get('typeName', '')
		self._skillName: str = data.get('skillName', '')
		self._parentLocation: int = data.get('parentLocation', 0)
		self._deviceType: DeviceType = self.DeviceManager.getDeviceType(self._skillName, self._typeName)

		if not self._deviceType:
			self.logError(f'Failed retrieving device type for device {self._typeName}')
			raise DeviceTypeUndefined(self._typeName)

		self._abilities: int = -1 if not data.get('abilities', None) else self.setAbilities(data['abilities'])
		self._deviceParams: Dict = json.loads(data.get('deviceParams', '{}'))
		self._displayName: str = data.get('displayName', '')
		self._connected: bool = False

		# Settings are for UI, all the components use the same variable
		self._settings = json.loads(data.get('settings', '{}')) if isinstance(data.get('settings', '{}'), str) else data.get('settings', dict())
		settings = {
			'x': 0,
			'y': 0,
			'z': len(self.DeviceManager.devices),
			'w': 50,
			'h': 50,
			'r': 0
		}

		self._settings = {**settings, **self._settings}
		self._lastContact: int = 0

		if not self._displayName:
			self._displayName = self._typeName

		self._deviceConfigs: Dict = json.loads(data.get('deviceConfigs', '{}'))

		self._heartbeatRate = self._deviceConfigs.get('heartbeatRate', self.deviceType.heartbeatRate)
		self._deviceConfigs.setdefault('displayName', self._displayName)
		self._deviceConfigs.setdefault('heartbeatRate', self._heartbeatRate)

		if self._id == -1:
			self.saveToDB()


	def getAbilities(self) -> bin:
		"""
		Returns the device's abilities
		:return: a bitmask of the device's abilities
		"""
		if self._abilities == -1:
			return self._deviceType.abilities
		else:
			return self._abilities


	def hasAbilities(self, abilities: List[DeviceAbility]) -> bool:
		"""
		Checks if that device has the given abilities
		:param abilities: a list of DeviceAbility
		:return: boolean
		"""
		if self._abilities == -1:
			return self._deviceType.hasAbilities(abilities)
		else:
			check = 0
			for ability in abilities:
				check |= ability.value

			return self._abilities & check == check


	def setAbilities(self, abilities: List[DeviceAbility]):
		"""
		Sets this device's abilities, based on a bitmask
		:param abilities:
		:return:
		"""
		self._abilities = 0
		for ability in abilities:
			self._abilities |= ability.value


	# noinspection SqlResolve
	def saveToDB(self):
		"""
		Updates or inserts this device in DB
		:return:
		"""
		if self._id != -1:
			self.DatabaseManager.replace(
				tableName=self.DeviceManager.DB_DEVICE,
				query='REPLACE INTO :__table__ (id, uid, parentLocation, typeName, skillName, settings, displayName, deviceParams, deviceConfigs) VALUES (:id, :uid, :parentLocation, :typeName, :skillName, :settings, :displayName, :deviceParams, :deviceConfigs)',
				callerName=self.DeviceManager.name,
				values={
					'id'             : self._id,
					'uid'            : self._uid,
					'parentLocation' : self._parentLocation,
					'typeName'       : self._typeName,
					'skillName'      : self._skillName,
					'settings'       : json.dumps(self._settings),
					'displayName'    : self._displayName,
					'deviceParams'   : json.dumps(self._deviceParams),
					'deviceConfigs'  : json.dumps(self._deviceConfigs)
				}
			)
			self.publishDevice()
		else:
			deviceId = self.DatabaseManager.insert(
				tableName=self.DeviceManager.DB_DEVICE,
				callerName=self.DeviceManager.name,
				values={
					'uid'            : self._uid,
					'parentLocation' : self._parentLocation,
					'typeName'       : self._typeName,
					'skillName'      : self._skillName,
					'settings'       : json.dumps(self._settings),
					'displayName'    : self._displayName,
					'deviceParams'   : json.dumps(self._deviceParams),
					'deviceConfigs'  : json.dumps(self._deviceConfigs)
				}
			)

			self._id = deviceId

	def getLocation(self) -> Optional[Location]:
		return self.LocationManager.getLocation(locId=self.parentLocation)


	def publishDevice(self):
		"""
		Whenever something changes on the device, the device data are published over mqtt
		to refresh the UI per exemple
		:return:
		"""
		self.MqttManager.publish(constants.TOPIC_DEVICE_UPDATED, payload={'uid': self._uid, 'device': self.toDict()})


	def pairingDone(self, uid: str):
		"""
		Called whenever a pairing procedure succeeded
		:param uid: the attributed uid
		:return:
		"""
		self._uid = uid
		self.saveToDB()


	@property
	def connected(self) -> bool:
		"""
		Returns wheather or not this device is connected
		:return:
		"""
		return self._connected


	@connected.setter
	def connected(self, value: bool):
		"""
		Sets device connection status
		:param value: bool
		:return:
		"""
		self._connected = value


	@property
	def paired(self) -> bool:
		return self._uid != ''


	@property
	def heartbeatRate(self) -> bool:
		return self._heartbeatRate


	@property
	def deviceTypeName(self) -> str:
		return self._typeName


	@property
	def deviceType(self) -> DeviceType:
		return self._deviceType


	@property
	def parentLocation(self) -> int:
		return self._parentLocation


	@parentLocation.setter
	def parentLocation(self, value: int):
		self._parentLocation = value


	@property
	def skillName(self) -> str:
		return self._skillName


	@property
	def id(self) -> int:
		return self._id


	@property
	def uid(self) -> str:
		return self._uid

	@property
	def displayName(self) -> str:
		return self._displayName


	@displayName.setter
	def displayName(self, value: str):
		self._displayName = value


	def toDict(self) -> dict:
		return {
			'abilities'             : bin(self.getAbilities()),
			'connected'             : self._connected,
			'deviceParams'          : self._deviceParams,
			'displayName'           : self._displayName,
			'settings'              : self._settings,
			'deviceConfigs'         : self._deviceConfigs,
			'id'                    : self._id,
			'lastContact'           : self._lastContact,
			'parentLocation'        : self._parentLocation,
			'skillName'             : self._skillName,
			'typeName'              : self._typeName,
			'uid'                   : self._uid,
			'heartbeatRate'         : self._heartbeatRate,
			'allowHeartbeatOverride': self.deviceType.allowHeartbeatOverride
		}


	def getDeviceIcon(self) -> Path:
		"""
		Return the path of the icon representing the current status of the device
		e.g. a light bulb can be on or off and display its status
		:return: the icon file path
		"""
		return Path(f'{self.Commons.rootDir()}/skills/{self.skillName}/devices/img/{self._typeName}.png')


	def updateSettings(self, settings: dict):
		self._settings = {**self._settings, **settings}


	def getParam(self, key: str, default: Any = False) -> Any:
		return self._deviceParams.get(key, default)


	def updateParams(self, key: str, value: Any):
		self._deviceParams[key] = value
		self.saveToDB()


	def onUIClick(self):
		if not self.paired:
			self.DeviceManager.startBroadcastingForNewDevice(self)


	def linkedTo(self, targetLocation: int) -> bool:
		"""
		Checks if this device is linked to the given location
		:param targetLocation: int
		:return: bool
		"""
		for link in self.DeviceManager.deviceLinks.values():
			if link.deviceId == self.id and link.targetLocation == targetLocation:
				return True
		return False


	def __repr__(self):
		return f'Device({self._id} - {self._displayName}, uid({self._uid}), Location({self._parentLocation}))'


	def __eq__(self, other):
		return other and self._uid == other.uid


	@classmethod
	def getDeviceTypeDefinition(cls) -> dict:
		raise NotImplementedError
