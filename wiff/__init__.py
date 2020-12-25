"""
WIFF -- Waveform Interchange File Format

This is a combination of files that are similar to the generic EA IFF 85 chunk format (inspired AIFF, RIFF, PNG, JFIF, etc)
However, IFF is limited to 32-bit chunk lengths which is inadequate and this expands to 64-bit.

The same chunk format is used for a couple types of chunks:
	- Informative that contains information about the entire dataset ("recording")
	- Waveform files to permit slicing up ("segments") large datasets into multiple files
	- Annotation files to add markers at various frames in the files

Terminology
* A recording is the entirety of recorded data with a specified number of channels and specified number of frames of data
* A recording is broken into segments consisting of multiple frames
* A frame consists of samples across all present channels in a segment at a given point in time
* A channel is a specific binary data source of data that is piece-wise present (not present sample-by-sample, but over a continous time period)
* Frame index is the index into the frames from zero (start of recording) to N (last frame of the recording)
* An annotation is a marker associated to a frame or frames that gives meaning beyond the raw binary data; interpretive information

Assumptions
* Each channel has a fixed bit size and does not change throughout the recording
* Fixed number of total channels throughout the recording
* Sampling rate is fixed throughout the recording and across channels
* Segments can have different sets of active channels
* One segment per WIFFWAVE chunk, one WIFFWAVE chunk per segment
* Essentially no limit on duration of recording; entire recording can span any number of files
  effectively limited by the WIFFWAVE.ChunkID 32-bit unique ID and 64-bit size of chunks
* Annotations are supported that can mark a specific frame, or range of frames
"""

WIFF_VERSION = 2

import datetime
import os

from sqlitehelper import SH, DBTable, DBCol, DBColROWID

def _now():
	datetime.datetime.utcnow()

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

	def setpragma(self):
		# Application ID is the 32-bit value for WIFF
		a = 'WIFF'.encode('ascii')
		b = (a[0] << 24) + (a[1] << 16) + (a[2] << 8) + (a[3])
		self.begin()
		self.execute("pragma application_id=%d" % b)
		# Other pragmas?
		self.commit()



class _WIFF_obj:
	def __init__(self, w):
		self._w = w
		self._db = w.db

class _WIFF_obj_list(_WIFF_obj):
	def keys(self):
		res = self.sub_d.select('rowid')
		rows = [_['rowid'] for _ in res]
		return rows

	def values(self):
		_t = self._sub_type
		return [_t(self._w, _) for _ in self.keys()]

	def items(self):
		return [(_, _t(self._w, _)) for _ in self.keys()]

	def __iter__(self):
		for k in self.keys():
			yield k

	def __len__(self):
		return self._sub_d.num_rows()

	def __getitem__(self, k):
		return self._sub_type(self._w, k)

class _WIFF_obj_item(_WIFF_obj):
	def __init__(self, w, _id, meta_name):
		super().__init__(w)

		self._sub_d = getattr(w.db, meta_name)

		self._id = _id

		self.refresh()

	def refresh(self):
		self._data = self._sub_d.select_one('*', '`rowid`=?', [self._id])

	@property
	def id(self): return self._id

class WIFF_recordings(_WIFF_obj_list):
	def __init__(self, w):
		self._sub_d = w.db.recording
		self._sub_type = WIFF_recording

		super().__init__(w)

class WIFF_recording(_WIFF_obj_item):
	def __init__(self, w, _id):
		super().__init__(w, _id, 'recording')

	@property
	def start(self): return self._data['start']

	@property
	def end(self): return self._data['end']

	@property
	def description(self): return self._data['description']

	@property
	def sampling(self): return self._data['sampling']

class WIFF_segments(_WIFF_obj_list):
	def __init__(self, w):
		self._sub_d = w.db.segment
		self._sub_type = WIFF_segment

		super().__init__(w)

class WIFF_segment(_WIFF_obj_item):
	def __init__(self, w, _id):
		super().__init__(w, _id, 'segment')

	@property
	def id_recording(self): return self._data['id_recording']

	@property
	def recording(self): return self._w.recording[ self._data['id_recording'] ]

	@property
	def idx(self): return self._data['idx']

	@property
	def fidx_start(self): return self._data['fidx_start']

	@property
	def fidx_end(self): return self._data['fidx_end']

	@property
	def channelset_id(self): return self._data['channelset_id']

	@property
	def id_blob(self): return self._data['id_blob']

	@property
	def blob(self): return self._w.blob[ self._data['id_blob'] ]

class WIFF_blobs(_WIFF_obj_list):
	def __init__(self, w):
		self._sub_d = w.db.blob
		self._sub_type = WIFF_blob

		super().__init__(w)

class WIFF_blob(_WIFF_obj_item):
	def __init__(self, w, _id):
		super().__init__(w, _id, 'blob')

	@property
	def compression(self): return self._data['compression']

	@property
	def data(self): return self._data['data']

class WIFF_metas(_WIFF_obj_list):
	def __init__(self, w):
		self._sub_d = w.db.meta
		self._sub_type = WIFF_meta

		super().__init__(w)

class WIFF_meta(_WIFF_obj_item):
	def __init__(self, w, _id):
		super().__init__(w, _id, 'meta')

	@property
	def key(self): return self._data['key']

	@property
	def type(self): return self._data['type']

	@property
	def raw_value(self):
		return self._data['value']

	@property
	def value(self):
		t = self.type
		v = self.raw_value

		if t == 'int':
			return int(v)
		elif t == 'str':
			return v
		elif t == 'datetime':
			return datetime.datetime.strptime(v, "%Y-%m-%d %H:%M:%S.%f")
		elif t == 'blob':
			# Interpret value as an id_blob
			return WIFF_blob(self._w, int(v))
		else:
			raise TypeError("Unrecognized meta value type '%s' for value '%s'" % (t,v))

class WIFF_channels(_WIFF_obj_list):
	def __init__(self, w):
		self._sub_d = w.db.channel
		self._sub_type = WIFF_channel

		super().__init__(w)

class WIFF_channel(_WIFF_obj_item):
	def __init__(self, w, _id):
		super().__init__(w, _id, 'channel')

	@property
	def id_recording(self): return self._data['id_recording']

	@property
	def idx(self): return self._data['idx']

	@property
	def bits(self): return self._data['bits']

	@property
	def name(self): return self._data['name']

	@property
	def unit(self): return self._data['unit']

	@property
	def comment(self): return self._data['comment']

class WIFF_channelsets(_WIFF_obj_list):
	def __init__(self, w):
		self._sub_d = w.db.channelset
		self._sub_type = WIFF_channelset

		super().__init__(w)

class WIFF_channelset(_WIFF_obj_item):
	def __init__(self, w, _id):
		super().__init__(w, _id, 'channelset')

	@property
	def set(self): return self._data['set']

	@property
	def id_channel(self): return self._data['id_channel']

	@property
	def channel(self): return WIFF_channel(self._w, self._data['id_channel'])

class WIFF_annotations(_WIFF_obj_list):
	def __init__(self, w):
		self._sub_d = w.db.annotation
		self._sub_type = WIFF_annotation

		super().__init__(w)

class WIFF_annotation(_WIFF_obj_item):
	def __init__(self, w, _id):
		super().__init__(w, _id, 'annotation')

	@property
	def id_recording(self): return self._data['id_recording']

	@property
	def fidx_start(self): return self._data['fidx_start']

	@property
	def fidx_end(self): return self._data['fidx_end']

	@property
	def type(self): return self._data['type']

	@property
	def comment(self): return self._data['comment']

	@property
	def marker(self): return self._data['marker']

	@property
	def data(self): return self._data['data']


class WIFF:
	def __init__(self, fname):
		self.db = wiffdb(fname)
		self.db.open()

		self.recording = WIFF_recordings(self)
		self.segment = WIFF_segments(self)
		self.blob = WIFF_blobs(self)
		self.meta = WIFF_metas(self)
		self.channel = WIFF_channels(self)
		self.channelset = WIFF_channelsets(self)
		self.annotation = WIFF_annotations(self)

	@classmethod
	def open(cls, fname):
		if not os.path.exists(fname):
			raise ValueError("File not found '%s'" % fname)

		# Make object
		w = cls(fname)

		# TODO: verify basics of the database

		return w

	@classmethod
	def new(cls, fname, props):
		if os.path.exists(fname):
			raise ValueError("File already exists '%s'" % fname)

		w = cls(fname)

		# Make schema
		w.db.MakeDatabaseSchema()

		# Set pragma's
		w.db.setpragma()

		# Initialize tables
		w.db.begin()
		id_r = w.db.recording.insert(start=props['start'], end=props['end'], description=props['description'], sampling=props['fs'])

		# Meta data about the recording
		w.db.meta.insert(key='WIFF.version', type='int', value='2')
		w.db.meta.insert(key='WIFF.ctime', type='datetime', value=datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f"))

		# Set channels
		for c in props['channels']:
			w.db.channel.insert(id_recording=id_r, idx=c['idx'], name=c['name'], bits=c['bits'], unit=c['unit'], comment=c['comment'])
		w.db.commit()

		return w

	def add_segment(self, id_recording, channels, fidx_start, fidx_end, data, compression=None):
		self.db.begin()

		# Get maximum index and use next available (zero-based)
		res = self.db.segment.select('idx', '`id_recording`=?', [id_recording])
		rows = [_['idx'] for _ in res]
		if len(rows):
			idx = max(rows) + 1
		else:
			idx = 1

		# Make a channel set
		res = self.db.channelset.select('set')
		rows = [_['set'] for _ in res]
		if len(rows):
			chanset = row['set'] + 1
		else:
			chanset = 1

		# Add each channel to the set
		for c in channels:
			self.db.channelset.insert(set=chanset, id_channel=c)

		# Add data and segment
		id_blob = self.db.blob.insert(compression=compression, data=data)
		id_segment = self.db.segment.insert(id_recording=id_recording, idx=idx, fidx_start=fidx_start, fidx_end=fidx_end, channelset_id=chanset, id_blob=id_blob)

		# Make changes
		self.db.commit()

		return id_segment



def open(fname):
	"""
	Open an existing WIFF file.
	"""
	return WIFF.open(fname)

def new(fname, props, force=False):
	"""
	@props -- dictionary including:
		'start'			datetime objects
		'end'			datetime objects
		'description'	string describing the recording
		'fs'			sampling frequency (int)
		'channels'		list of channels
			'idx'			channel index (zero based)
			'name'			name of the channel
			'bit'			bits (int) of each measurement
			'unit'			physical units of the measurement (str)
			'comment'		Arbitrary comment on the channel
		'files'			list of files, probably empty (except for INFO file) for a new recording
	"""

	w = WIFF.new(fname, props)
	return w

