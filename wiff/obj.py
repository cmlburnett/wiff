
import datetime

# ------------------------------------------------------------------------
# ------------------------------------------------------------------------
# Generic base classes

class _WIFF_obj:
	"""
	Every object accepts the main WIFF object and copies in the DB object.
	"""

	def __init__(self, w):
		self._w = w
		self._db = w.db

class _WIFF_obj_list(_WIFF_obj):
	"""
	Intended for list item style access to a type using the rowid as the key.

	keys(), values(), items() return ata like the same functions on dict()
	len() call on this object does a row count.
	foo[rowid] gets a specific item
	"""

	def _query(self):
		return self.sub_d.select('rowid')
	def _query_len(self):
		return self._sub_d.num_rows()

	def keys(self):
		res = self._query()
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
		return self._query_len()

	def __getitem__(self, k):
		return self._sub_type(self._w, k)

class _WIFF_obj_item(_WIFF_obj):
	"""
	Intended for individual object access

	refresh() reloads the data from the database as no attempt is made to keep this object consistent.
	id property is available on all objects as the rowid value.
	"""

	def __init__(self, w, _id, meta_name):
		"""
		Provide the rowid as @_id and the @meta_name is the name (eg, 'recording') which should be the table name in the DB.
		"""

		super().__init__(w)

		# Pull out the sub table object from the database for this object
		self._sub_d = getattr(w.db, meta_name)

		self._id = _id

		# Load in data now (rather than lazy loading)
		self.refresh()

	def refresh(self):
		"""Reload the data from the database"""
		self._data = self._sub_d.select_one('*', '`rowid`=?', [self._id])

	@property
	def id(self): return self._id

# ------------------------------------------------------------------------
# ------------------------------------------------------------------------
# Specific object types

class WIFF_recordings(_WIFF_obj_list):
	def __init__(self, w):
		self._sub_d = w.db.recording
		self._sub_type = WIFF_recording

		super().__init__(w)

class WIFF_recording_segments(_WIFF_obj_list):
	def __init__(self, w, id_recording):
		self._id_recording = id_recording

		self._sub_d = w.db.segment
		self._sub_type = WIFF_segment

		super().__init__(w)

	def _query(self):
		return self._sub_d.select('rowid', '`id_recording`=?', [self._id_recording])
	def _query_len(self):
		return self._sub_d.num_rows('`id_recording`=%d' % self._id_recording)

class WIFF_recording_metas(_WIFF_obj_list):
	def __init__(self, w, id_recording):
		self._id_recording = id_recording

		self._sub_d = w.db.meta
		self._sub_type = WIFF_meta

		super().__init__(w)

	def _query(self):
		return self._sub_d.select('rowid', '`id_recording`=?', [self._id_recording])
	def _query_len(self):
		return self._sub_d.num_rows('`id_recording`=%d' % self._id_recording)

class WIFF_recording_channels(_WIFF_obj_list):
	def __init__(self, w, id_recording):
		self._id_recording = id_recording

		self._sub_d = w.db.channel
		self._sub_type = WIFF_channel

		super().__init__(w)

	def _query(self):
		return self._sub_d.select('rowid', '`id_recording`=?', [self._id_recording])
	def _query_len(self):
		return self._sub_d.num_rows('`id_recording`=%d' % self._id_recording)

class WIFF_recording_frames(_WIFF_obj):
	def __init__(self, w, id_recording):
		self._id_recording = id_recording

		super().__init__(w)

	def __getitem__(self, k):
		row = self._db.segment.select_one(['rowid','id_blob'], '`fidx_start`<=? and `fidx_end`>=? and `id_recording`=?', [k,k, self._id_recording])
		if row is None:
			raise ValueError("No segment for this recording (%d) contains the frame %d" % (self._id_recording, k))

		seg = WIFF_segment(self._w, row['rowid'])
		b = WIFF_blob(self._w, row['id_blob'])

		ret = []
		# Calculate sum total of channels
		stride = []
		for cs in seg.channelset:
			# Get number of bytes needed for the channel
			q,r = divmod(cs.channel.bits, 8)
			if r:
				stride.append(q+1)
			else:
				stride.append(q)

		# How many frames into the blob to read
		offset = (k - seg.fidx_start) * sum(stride)

		for s in stride:
			ret.append( b.data[offset:offset+s] )
			offset += s

		return tuple(ret)



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

	@property
	def segment(self): return WIFF_recording_segments(self._w, self._id)

	@property
	def meta(self): return WIFF_recording_metas(self._w, self._id)

	@property
	def channel(self): return WIFF_recording_channels(self._w, self._id)

	@property
	def frame(self): return WIFF_recording_frames(self._w, self._id)

# ----------------------------------------

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
	def channelset(self):
		res = self._db.channelset.select('rowid', '`set`=?', [self._data['channelset_id']])
		return [WIFF_channelset(self._w, _['rowid']) for _ in res]

	@property
	def id_blob(self): return self._data['id_blob']

	@property
	def blob(self): return self._w.blob[ self._data['id_blob'] ]

# ----------------------------------------

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

# ----------------------------------------

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

# ----------------------------------------

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

# ----------------------------------------

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

# ----------------------------------------

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
