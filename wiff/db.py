

from sqlitehelper import SH, DBTable, DBCol, DBColROWID

class wiffdb(SH):
	__schema__ = [
		# General settings (not meta data)
		DBTable('settings',
			DBColROWID(),
			DBCol('key', 'text'),
			DBCol('value', 'text'),
		),
		# Recording consists of multiple segments
		DBTable('recording',
			DBColROWID(),
			DBCol('start', 'datetime'),
			DBCol('end', 'datetime'),
			DBCol('description', 'text'),
			DBCol('sampling', 'integer'),
		),
		# Each segment contains a number of frames of samples
		DBTable('segment',
			DBColROWID(),
			DBCol('id_recording', 'integer'),
			DBCol('idx', 'integer'),
			DBCol('fidx_start', 'integer'),
			DBCol('fidx_end', 'integer'),
			DBCol('channelset_id', 'integer'),
			DBCol('stride', 'integer'),
			DBCol('id_blob', 'integer'),
		),
		DBTable('blob',
			DBColROWID(),
			DBCol('compression', 'text'),
			DBCol('data', 'blob'),
		),

		# Key/value pairs of metadata for a recording
		DBTable('meta',
			DBColROWID(),
			DBCol('id_recording', 'integer'),
			DBCol('key', 'text'),
			DBCol('type', 'text'),
			DBCol('value', 'text'),
		),
		# Recording consists of any number of channels
		DBTable('channel',
			DBColROWID(),
			DBCol('id_recording', 'integer'),
			DBCol('idx', 'integer'),
			DBCol('bits', 'integer'),
			DBCol('storage', 'integer'),
			DBCol('name', 'text'),
			DBCol('unit', 'text'),
			DBCol('comment', 'text'),
			DBCol('digitalminvalue', 'integer'),
			DBCol('digitalmaxvalue', 'integer'),
			DBCol('analogminvalue', 'real'),
			DBCol('analogmaxvalue', 'real'),
		),
		# Set of channels used in a segment, multiple rows with the same `set` value == segment.channelset
		DBTable('channelset',
			DBColROWID(),
			DBCol('set', 'integer'),
			DBCol('id_channel', 'integer'),
		),

		# Annotations apply to a range of frames to provide meaning
		# to that range of frames
		DBTable('annotation',
			DBColROWID(),
			DBCol('id_recording', 'integer'),
			DBCol('id_channelset', 'integer'),
			DBCol('fidx_start', 'integer'),
			DBCol('fidx_end', 'integer'),
			DBCol('type', 'text'),
			DBCol('comment', 'text'),
			DBCol('marker', 'text'),
			DBCol('data', 'integer'),
		),
	]

	def setpragma(self, app_id):
		# Application ID is the 32-bit value for WIFF
		with self.transaction():
			self.execute(None, 'pragma', "pragma application_id=%d" % app_id)
			# Other pragmas?

