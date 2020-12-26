

from sqlitehelper import SH, DBTable, DBCol, DBColROWID

class wiffdb(SH):
	__schema__ = [
		# Recording consists of multiple segments
		DBTable('recording',
			DBColROWID(),
			DBCol('start', 'datetime'),
			DBCol('end', 'datetime'),
			DBCol('description', 'text'),
			DBCol('sampling', 'int'),
		),
		# Each segment contains a number of frames of samples
		DBTable('segment',
			DBColROWID(),
			DBCol('id_recording', 'int'),
			DBCol('idx', 'int'),
			DBCol('fidx_start', 'int'),
			DBCol('fidx_end', 'int'),
			DBCol('channelset_id', 'int'),
			DBCol('stride', 'int'),
			DBCol('id_blob', 'int'),
		),
		DBTable('blob',
			DBColROWID(),
			DBCol('compression', 'text'),
			DBCol('data', 'blob'),
		),

		# Key/value pairs of metadata for a recording
		DBTable('meta',
			DBColROWID(),
			DBCol('id_recording', 'int'),
			DBCol('key', 'text'),
			DBCol('type', 'text'),
			DBCol('value', 'text'),
		),
		# Recording consists of any number of channels
		DBTable('channel',
			DBColROWID(),
			DBCol('id_recording', 'int'),
			DBCol('idx', 'int'),
			DBCol('bits', 'int'),
			DBCol('storage', 'int'),
			DBCol('name', 'text'),
			DBCol('unit', 'text'),
			DBCol('comment', 'text'),
		),
		# Set of channels used in a segment, multiple rows with the same `set` value == segment.channelset
		DBTable('channelset',
			DBColROWID(),
			DBCol('set', 'int'),
			DBCol('id_channel', 'int'),
		),

		# Annotations apply to a range of frames to provide meaning
		# to that range of frames
		DBTable('annotation',
			DBColROWID(),
			DBCol('id_recording', 'int'),
			DBCol('fidx_start', 'int'),
			DBCol('fidx_end', 'int'),
			DBCol('type', 'text'),
			DBCol('comment', 'text'),
			DBCol('marker', 'text'),
			DBCol('data', 'int'),
		),
	]

	def setpragma(self, app_id):
		# Application ID is the 32-bit value for WIFF
		self.begin()
		self.execute("pragma application_id=%d" % app_id)
		# Other pragmas?
		self.commit()

