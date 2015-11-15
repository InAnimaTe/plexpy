﻿# This file is part of PlexPy.
#
#  PlexPy is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  PlexPy is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with PlexPy.  If not, see <http://www.gnu.org/licenses/>.

from plexpy import logger, datatables, common, database, helpers

import datetime


class DataFactory(object):
    """
    Retrieve and process data from the monitor database
    """

    def __init__(self):
        pass

    def get_history(self, kwargs=None, custom_where=None, grouping=0, watched_percent=85):
        data_tables = datatables.DataTables()

        group_by = ['session_history.reference_id'] if grouping else ['session_history.id']

        columns = ['session_history.reference_id',
                   'session_history.id',
                   'started AS date',
                   'MIN(started) AS started',
                   'MAX(stopped) AS stopped',
                   'SUM(CASE WHEN stopped > 0 THEN (stopped - started) ELSE 0 END) - \
		            SUM(CASE WHEN paused_counter IS NULL THEN 0 ELSE paused_counter END) AS duration',
                   'SUM(CASE WHEN paused_counter IS NULL THEN 0 ELSE paused_counter END) AS paused_counter',
                   'session_history.user_id',
                   'session_history.user',
                   '(CASE WHEN users.friendly_name IS NULL THEN users.username ELSE users.friendly_name END) as friendly_name',
                   'platform',
                   'player',
                   'ip_address',
                   'session_history_metadata.media_type',
                   'session_history_metadata.rating_key',
                   'session_history_metadata.parent_rating_key',
                   'session_history_metadata.grandparent_rating_key',
                   'session_history_metadata.full_title',
                   'session_history_metadata.parent_title',
                   'session_history_metadata.year',
                   'session_history_metadata.media_index',
                   'session_history_metadata.parent_media_index',
                   'session_history_metadata.thumb',
                   'session_history_metadata.parent_thumb',
                   'session_history_metadata.grandparent_thumb',
                   '((CASE WHEN view_offset IS NULL THEN 0.1 ELSE view_offset * 1.0 END) / \
		            (CASE WHEN session_history_metadata.duration IS NULL THEN 1.0 ELSE session_history_metadata.duration * 1.0 END) * 100) AS percent_complete',
                   'session_history_media_info.video_decision',
                   'session_history_media_info.audio_decision',
                   'COUNT(*) AS group_count',
                   'GROUP_CONCAT(session_history.id) AS group_ids'
                   ]
        try:
            query = data_tables.ssp_query(table_name='session_history',
                                          columns=columns,
                                          custom_where=custom_where,
                                          group_by=group_by,
                                          join_types=['LEFT OUTER JOIN',
                                                      'JOIN',
                                                      'JOIN'],
                                          join_tables=['users',
                                                       'session_history_metadata',
                                                       'session_history_media_info'],
                                          join_evals=[['session_history.user_id', 'users.user_id'],
                                                      ['session_history.id', 'session_history_metadata.id'],
                                                      ['session_history.id', 'session_history_media_info.id']],
                                          kwargs=kwargs)
        except:
            logger.warn("Unable to execute database query.")
            return {'recordsFiltered': 0,
                    'recordsTotal': 0,
                    'draw': 0,
                    'data': 'null',
                    'error': 'Unable to execute database query.'}

        history = query['result']

        rows = []
        for item in history:
            if item["media_type"] == 'episode' and item["parent_thumb"]:
                thumb = item["parent_thumb"]
            elif item["media_type"] == 'episode':
                thumb = item["grandparent_thumb"]
            else:
                thumb = item["thumb"]

            if item['percent_complete'] >= watched_percent:
                watched_status = 1
            elif item['percent_complete'] >= watched_percent/2:
                watched_status = 0.5
            else:
                watched_status = 0

            # Rename Mystery platform names
            platform = common.PLATFORM_NAME_OVERRIDES.get(item["platform"], item["platform"])

            row = {"reference_id": item["reference_id"],
                   "id": item["id"],
                   "date": item["date"],
                   "started": item["started"],
                   "stopped": item["stopped"],
                   "duration": item["duration"],
                   "paused_counter": item["paused_counter"],
                   "user_id": item["user_id"],
                   "user": item["user"],
                   "friendly_name": item["friendly_name"],
                   "platform": platform,
                   "player": item['player'],
                   "ip_address": item["ip_address"],
                   "media_type": item["media_type"],
                   "rating_key": item["rating_key"],
                   "parent_rating_key": item["parent_rating_key"],
                   "grandparent_rating_key": item["grandparent_rating_key"],
                   "full_title": item["full_title"],
                   "parent_title": item["parent_title"],
                   "year": item["year"],
                   "media_index": item["media_index"],
                   "parent_media_index": item["parent_media_index"],
                   "thumb": thumb,
                   "video_decision": item["video_decision"],
                   "audio_decision": item["audio_decision"],
                   "percent_complete": int(round(item['percent_complete'])),
                   "watched_status": watched_status,
                   "group_count": item["group_count"],
                   "group_ids": item["group_ids"]
                   }

            rows.append(row)

        dict = {'recordsFiltered': query['filteredCount'],
                'recordsTotal': query['totalCount'],
                'data': rows,
                'draw': query['draw']
        }

        return dict

    def get_home_stats(self, time_range='30', stats_type=0, stats_count='5', stats_cards='', notify_watched_percent='85'):
        monitor_db = database.MonitorDatabase()

        sort_type = 'total_plays' if stats_type == 0 else 'total_duration'

        home_stats = []

        for stat in stats_cards:
            if stat == 'top_tv':
                top_tv = []
                try:
                    query = 'SELECT session_history_metadata.id, ' \
                            'session_history_metadata.grandparent_title, ' \
                            'COUNT(session_history_metadata.grandparent_title) as total_plays, ' \
                            'SUM(case when session_history.stopped > 0 ' \
                            'then (session_history.stopped - session_history.started) ' \
                            ' - (case when session_history.paused_counter is NULL then 0 else session_history.paused_counter end) ' \
                            'else 0 end) as total_duration, ' \
                            'session_history_metadata.grandparent_rating_key, ' \
                            'MAX(session_history.started) as last_watch,' \
                            'session_history_metadata.grandparent_thumb ' \
                            'FROM session_history_metadata ' \
                            'JOIN session_history on session_history_metadata.id = session_history.id ' \
                            'WHERE datetime(session_history.stopped, "unixepoch", "localtime") ' \
                            '>= datetime("now", "-%s days", "localtime") ' \
                            'AND session_history_metadata.media_type = "episode" ' \
                            'GROUP BY session_history_metadata.grandparent_title ' \
                            'ORDER BY %s DESC LIMIT %s' % (time_range, sort_type, stats_count)
                    result = monitor_db.select(query)
                except:
                    logger.warn("Unable to execute database query for get_home_stats: top_tv.")
                    return None

                for item in result:
                    row = {'title': item['grandparent_title'],
                           'total_plays': item['total_plays'],
                           'total_duration': item['total_duration'],
                           'users_watched': '',
                           'rating_key': item['grandparent_rating_key'],
                           'last_play': item['last_watch'],
                           'grandparent_thumb': item['grandparent_thumb'],
                           'thumb': '',
                           'user': '',
                           'friendly_name': '',
                           'platform_type': '',
                           'platform': '',
                           'row_id': item['id']
                           }
                    top_tv.append(row)

                home_stats.append({'stat_id': stat,
                                   'stat_type': sort_type,
                                   'rows': top_tv})

            elif stat == 'popular_tv':
                popular_tv = []
                try:
                    query = 'SELECT session_history_metadata.id, ' \
                            'session_history_metadata.grandparent_title, ' \
                            'COUNT(DISTINCT session_history.user_id) as users_watched, ' \
                            'session_history_metadata.grandparent_rating_key, ' \
                            'MAX(session_history.started) as last_watch, ' \
                            'COUNT(session_history.id) as total_plays, ' \
                            'SUM(case when session_history.stopped > 0 ' \
                            'then (session_history.stopped - session_history.started) ' \
                            ' - (case when session_history.paused_counter is NULL then 0 else session_history.paused_counter end) ' \
                            'else 0 end) as total_duration, ' \
                            'session_history_metadata.grandparent_thumb ' \
                            'FROM session_history_metadata ' \
                            'JOIN session_history ON session_history_metadata.id = session_history.id ' \
                            'WHERE datetime(session_history.stopped, "unixepoch", "localtime") ' \
                            '>= datetime("now", "-%s days", "localtime") ' \
                            'AND session_history_metadata.media_type = "episode" ' \
                            'GROUP BY session_history_metadata.grandparent_title ' \
                            'ORDER BY users_watched DESC, %s DESC ' \
                            'LIMIT %s' % (time_range, sort_type, stats_count)
                    result = monitor_db.select(query)
                except:
                    logger.warn("Unable to execute database query for get_home_stats: popular_tv.")
                    return None

                for item in result:
                    row = {'title': item['grandparent_title'],
                           'users_watched': item['users_watched'],
                           'rating_key': item['grandparent_rating_key'],
                           'last_play': item['last_watch'],
                           'total_plays': item['total_plays'],
                           'grandparent_thumb': item['grandparent_thumb'],
                           'thumb': '',
                           'user': '',
                           'friendly_name': '',
                           'platform_type': '',
                           'platform': '',
                           'row_id': item['id']
                           }
                    popular_tv.append(row)

                home_stats.append({'stat_id': stat,
                                   'rows': popular_tv})

            elif stat == 'top_movies':
                top_movies = []
                try:
                    query = 'SELECT session_history_metadata.id, ' \
                            'session_history_metadata.full_title, ' \
                            'COUNT(session_history_metadata.full_title) as total_plays, ' \
                            'SUM(case when session_history.stopped > 0 ' \
                            'then (session_history.stopped - session_history.started) ' \
                            ' - (case when session_history.paused_counter is NULL then 0 else session_history.paused_counter end) ' \
                            'else 0 end) as total_duration, ' \
                            'session_history_metadata.rating_key, ' \
                            'MAX(session_history.started) as last_watch,' \
                            'session_history_metadata.thumb ' \
                            'FROM session_history_metadata ' \
                            'JOIN session_history on session_history_metadata.id = session_history.id ' \
                            'WHERE datetime(session_history.stopped, "unixepoch", "localtime") ' \
                            '>= datetime("now", "-%s days", "localtime") ' \
                            'AND session_history_metadata.media_type = "movie" ' \
                            'GROUP BY session_history_metadata.full_title ' \
                            'ORDER BY %s DESC LIMIT %s' % (time_range, sort_type, stats_count)
                    result = monitor_db.select(query)
                except:
                    logger.warn("Unable to execute database query for get_home_stats: top_movies.")
                    return None

                for item in result:
                    row = {'title': item['full_title'],
                           'total_plays': item['total_plays'],
                           'total_duration': item['total_duration'],
                           'users_watched': '',
                           'rating_key': item['rating_key'],
                           'last_play': item['last_watch'],
                           'grandparent_thumb': '',
                           'thumb': item['thumb'],
                           'user': '',
                           'friendly_name': '',
                           'platform_type': '',
                           'platform': '',
                           'row_id': item['id']
                           }
                    top_movies.append(row)

                home_stats.append({'stat_id': stat,
                                   'stat_type': sort_type,
                                   'rows': top_movies})

            elif stat == 'popular_movies':
                popular_movies = []
                try:
                    query = 'SELECT session_history_metadata.id, ' \
                            'session_history_metadata.full_title, ' \
                            'COUNT(DISTINCT session_history.user_id) as users_watched, ' \
                            'session_history_metadata.rating_key, ' \
                            'MAX(session_history.started) as last_watch, ' \
                            'COUNT(session_history.id) as total_plays, ' \
                            'SUM(case when session_history.stopped > 0 ' \
                            'then (session_history.stopped - session_history.started) ' \
                            ' - (case when session_history.paused_counter is NULL then 0 else session_history.paused_counter end) ' \
                            'else 0 end) as total_duration, ' \
                            'session_history_metadata.thumb ' \
                            'FROM session_history_metadata ' \
                            'JOIN session_history ON session_history_metadata.id = session_history.id ' \
                            'WHERE datetime(session_history.stopped, "unixepoch", "localtime") ' \
                            '>= datetime("now", "-%s days", "localtime") ' \
                            'AND session_history_metadata.media_type = "movie" ' \
                            'GROUP BY session_history_metadata.full_title ' \
                            'ORDER BY users_watched DESC, %s DESC ' \
                            'LIMIT %s' % (time_range, sort_type, stats_count)
                    result = monitor_db.select(query)
                except:
                    logger.warn("Unable to execute database query for get_home_stats: popular_movies.")
                    return None

                for item in result:
                    row = {'title': item['full_title'],
                           'users_watched': item['users_watched'],
                           'rating_key': item['rating_key'],
                           'last_play': item['last_watch'],
                           'total_plays': item['total_plays'],
                           'grandparent_thumb': '',
                           'thumb': item['thumb'],
                           'user': '',
                           'friendly_name': '',
                           'platform_type': '',
                           'platform': '',
                           'row_id': item['id']
                           }
                    popular_movies.append(row)

                home_stats.append({'stat_id': stat,
                                   'rows': popular_movies})

            elif stat == 'top_music':
                top_music = []
                try:
                    query = 'SELECT session_history_metadata.id, ' \
                            'session_history_metadata.grandparent_title, ' \
                            'COUNT(session_history_metadata.grandparent_title) as total_plays, ' \
                            'SUM(case when session_history.stopped > 0 ' \
                            'then (session_history.stopped - session_history.started) ' \
                            ' - (case when session_history.paused_counter is NULL then 0 else session_history.paused_counter end) ' \
                            'else 0 end) as total_duration, ' \
                            'session_history_metadata.grandparent_rating_key, ' \
                            'MAX(session_history.started) as last_watch,' \
                            'session_history_metadata.grandparent_thumb ' \
                            'FROM session_history_metadata ' \
                            'JOIN session_history on session_history_metadata.id = session_history.id ' \
                            'WHERE datetime(session_history.stopped, "unixepoch", "localtime") ' \
                            '>= datetime("now", "-%s days", "localtime") ' \
                            'AND session_history_metadata.media_type = "track" ' \
                            'GROUP BY session_history_metadata.grandparent_title ' \
                            'ORDER BY %s DESC LIMIT %s' % (time_range, sort_type, stats_count)
                    result = monitor_db.select(query)
                except:
                    logger.warn("Unable to execute database query for get_home_stats: top_music.")
                    return None

                for item in result:
                    row = {'title': item['grandparent_title'],
                           'total_plays': item['total_plays'],
                           'total_duration': item['total_duration'],
                           'users_watched': '',
                           'rating_key': item['grandparent_rating_key'],
                           'last_play': item['last_watch'],
                           'grandparent_thumb': item['grandparent_thumb'],
                           'thumb': '',
                           'user': '',
                           'friendly_name': '',
                           'platform_type': '',
                           'platform': '',
                           'row_id': item['id']
                           }
                    top_music.append(row)

                home_stats.append({'stat_id': stat,
                                   'stat_type': sort_type,
                                   'rows': top_music})

            elif stat == 'popular_music':
                popular_music = []
                try:
                    query = 'SELECT session_history_metadata.id, ' \
                            'session_history_metadata.grandparent_title, ' \
                            'COUNT(DISTINCT session_history.user_id) as users_watched, ' \
                            'session_history_metadata.grandparent_rating_key, ' \
                            'MAX(session_history.started) as last_watch, ' \
                            'COUNT(session_history.id) as total_plays, ' \
                            'SUM(case when session_history.stopped > 0 ' \
                            'then (session_history.stopped - session_history.started) ' \
                            ' - (case when session_history.paused_counter is NULL then 0 else session_history.paused_counter end) ' \
                            'else 0 end) as total_duration, ' \
                            'session_history_metadata.grandparent_thumb ' \
                            'FROM session_history_metadata ' \
                            'JOIN session_history ON session_history_metadata.id = session_history.id ' \
                            'WHERE datetime(session_history.stopped, "unixepoch", "localtime") ' \
                            '>= datetime("now", "-%s days", "localtime") ' \
                            'AND session_history_metadata.media_type = "track" ' \
                            'GROUP BY session_history_metadata.grandparent_title ' \
                            'ORDER BY users_watched DESC, %s DESC ' \
                            'LIMIT %s' % (time_range, sort_type, stats_count)
                    result = monitor_db.select(query)
                except:
                    logger.warn("Unable to execute database query for get_home_stats: popular_music.")
                    return None

                for item in result:
                    row = {'title': item['grandparent_title'],
                           'users_watched': item['users_watched'],
                           'rating_key': item['grandparent_rating_key'],
                           'last_play': item['last_watch'],
                           'total_plays': item['total_plays'],
                           'grandparent_thumb': item['grandparent_thumb'],
                           'thumb': '',
                           'user': '',
                           'friendly_name': '',
                           'platform_type': '',
                           'platform': '',
                           'row_id': item['id']
                           }
                    popular_music.append(row)

                home_stats.append({'stat_id': stat,
                                   'rows': popular_music})

            elif stat == 'top_users':
                top_users = []
                try:
                    query = 'SELECT session_history.user, ' \
                            '(case when users.friendly_name is null then users.username else ' \
                            'users.friendly_name end) as friendly_name,' \
                            'COUNT(session_history.id) as total_plays, ' \
                            'SUM(case when session_history.stopped > 0 ' \
                            'then (session_history.stopped - session_history.started) ' \
                            ' - (case when session_history.paused_counter is NULL then 0 else session_history.paused_counter end) ' \
                            'else 0 end) as total_duration, ' \
                            'MAX(session_history.started) as last_watch, ' \
                            'users.custom_avatar_url as thumb, ' \
                            'users.user_id ' \
                            'FROM session_history ' \
                            'JOIN session_history_metadata ON session_history.id = session_history_metadata.id ' \
                            'LEFT OUTER JOIN users ON session_history.user_id = users.user_id ' \
                            'WHERE datetime(session_history.stopped, "unixepoch", "localtime") >= ' \
                            'datetime("now", "-%s days", "localtime") '\
                            'GROUP BY session_history.user_id ' \
                            'ORDER BY %s DESC LIMIT %s' % (time_range, sort_type, stats_count)
                    result = monitor_db.select(query)
                except:
                    logger.warn("Unable to execute database query for get_home_stats: top_users.")
                    return None

                for item in result:
                    if not item['thumb'] or item['thumb'] == '':
                        user_thumb = common.DEFAULT_USER_THUMB
                    else:
                        user_thumb = item['thumb']

                    row = {'user': item['user'],
                           'user_id': item['user_id'],
                           'friendly_name': item['friendly_name'],
                           'total_plays': item['total_plays'],
                           'total_duration': item['total_duration'],
                           'last_play': item['last_watch'],
                           'user_thumb': user_thumb,
                           'grandparent_thumb': '',
                           'users_watched': '',
                           'rating_key': '',
                           'title': '',
                           'platform_type': '',
                           'platform': '',
                           'row_id': ''
                    }
                    top_users.append(row)

                home_stats.append({'stat_id': stat,
                                   'stat_type': sort_type,
                                   'rows': top_users})

            elif stat == 'top_platforms':
                top_platform = []

                try:
                    query = 'SELECT session_history.platform, ' \
                            'COUNT(session_history.id) as total_plays, ' \
                            'SUM(case when session_history.stopped > 0 ' \
                            'then (session_history.stopped - session_history.started) ' \
                            ' - (case when session_history.paused_counter is NULL then 0 else session_history.paused_counter end) ' \
                            'else 0 end) as total_duration, ' \
                            'MAX(session_history.started) as last_watch ' \
                            'FROM session_history ' \
                            'WHERE datetime(session_history.stopped, "unixepoch", "localtime") ' \
                            '>= datetime("now", "-%s days", "localtime") ' \
                            'GROUP BY session_history.platform ' \
                            'ORDER BY %s DESC LIMIT %s' % (time_range, sort_type, stats_count)
                    result = monitor_db.select(query)
                except:
                    logger.warn("Unable to execute database query for get_home_stats: top_platforms.")
                    return None

                for item in result:
                    # Rename Mystery platform names
                    platform_type = common.PLATFORM_NAME_OVERRIDES.get(item['platform'], item['platform'])

                    row = {'platform': item['platform'],
                           'total_plays': item['total_plays'],
                           'total_duration': item['total_duration'],
                           'last_play': item['last_watch'],
                           'platform_type': platform_type,
                           'title': '',
                           'thumb': '',
                           'grandparent_thumb': '',
                           'users_watched': '',
                           'rating_key': '',
                           'user': '',
                           'friendly_name': '',
                           'row_id': ''
                           }
                    top_platform.append(row)

                home_stats.append({'stat_id': stat,
                                   'stat_type': sort_type,
                                   'rows': top_platform})

            elif stat == 'last_watched':
                last_watched = []
                try:
                    query = 'SELECT session_history_metadata.id, ' \
                            'session_history.user, ' \
                            '(case when users.friendly_name is null then users.username else ' \
                            'users.friendly_name end) as friendly_name,' \
                            'users.user_id, ' \
                            'users.custom_avatar_url as user_thumb, ' \
                            'session_history_metadata.full_title, ' \
                            'session_history_metadata.rating_key, ' \
                            'session_history_metadata.thumb, ' \
                            'session_history_metadata.grandparent_thumb, ' \
                            'MAX(session_history.started) as last_watch, ' \
                            'session_history.player, ' \
                            '((CASE WHEN session_history.view_offset IS NULL THEN 0.1 ELSE \
                             session_history.view_offset * 1.0 END) / \
                             (CASE WHEN session_history_metadata.duration IS NULL THEN 1.0 ELSE \
                             session_history_metadata.duration * 1.0 END) * 100) as percent_complete ' \
                            'FROM session_history_metadata ' \
                            'JOIN session_history ON session_history_metadata.id = session_history.id ' \
                            'LEFT OUTER JOIN users ON session_history.user_id = users.user_id ' \
                            'WHERE datetime(session_history.stopped, "unixepoch", "localtime") ' \
                            '>= datetime("now", "-%s days", "localtime") ' \
                            'AND (session_history_metadata.media_type = "movie" ' \
                            'OR session_history_metadata.media_type = "episode") ' \
                            'AND percent_complete >= %s ' \
                            'GROUP BY session_history.id ' \
                            'ORDER BY last_watch DESC ' \
                            'LIMIT %s' % (time_range, notify_watched_percent, stats_count)
                    result = monitor_db.select(query)
                except:
                    logger.warn("Unable to execute database query for get_home_stats: last_watched.")
                    return None

                for item in result:
                    if not item['grandparent_thumb'] or item['grandparent_thumb'] == '':
                        thumb = item['thumb']
                    else:
                        thumb = item['grandparent_thumb']

                    row = {'row_id': item['id'],
                           'user': item['user'],
                           'friendly_name': item['friendly_name'],
                           'user_id': item['user_id'],
                           'user_thumb': item['user_thumb'],
                           'title': item['full_title'],
                           'rating_key': item['rating_key'],
                           'thumb': thumb,
                           'grandparent_thumb': item['grandparent_thumb'],
                           'last_watch': item['last_watch'],
                           'player': item['player']
                           }
                    last_watched.append(row)

                home_stats.append({'stat_id': stat,
                                   'rows': last_watched})

        return home_stats

    def get_stream_details(self, row_id=None):
        monitor_db = database.MonitorDatabase()

        if row_id:
            query = 'SELECT container, bitrate, video_resolution, width, height, aspect_ratio, video_framerate, ' \
                    'video_codec, audio_codec, audio_channels, video_decision, transcode_video_codec, transcode_height, ' \
                    'transcode_width, audio_decision, transcode_audio_codec, transcode_audio_channels, media_type, ' \
                    'title, grandparent_title ' \
                    'from session_history_media_info ' \
                    'join session_history_metadata on session_history_media_info.id = session_history_metadata.id ' \
                    'where session_history_media_info.id = ?'
            result = monitor_db.select(query, args=[row_id])
        else:
            return None

        stream_output = {}

        for item in result:
            stream_output = {'container': item['container'],
                             'bitrate': item['bitrate'],
                             'video_resolution': item['video_resolution'],
                             'width': item['width'],
                             'height': item['height'],
                             'aspect_ratio': item['aspect_ratio'],
                             'video_framerate': item['video_framerate'],
                             'video_codec': item['video_codec'],
                             'audio_codec': item['audio_codec'],
                             'audio_channels': item['audio_channels'],
                             'transcode_video_dec': item['video_decision'],
                             'transcode_video_codec': item['transcode_video_codec'],
                             'transcode_height': item['transcode_height'],
                             'transcode_width': item['transcode_width'],
                             'transcode_audio_dec': item['audio_decision'],
                             'transcode_audio_codec': item['transcode_audio_codec'],
                             'transcode_audio_channels': item['transcode_audio_channels'],
                             'media_type': item['media_type'],
                             'title': item['title'],
                             'grandparent_title': item['grandparent_title']
                             }

        return stream_output

    def get_recently_watched(self, user=None, user_id=None, limit='10'):
        monitor_db = database.MonitorDatabase()
        recently_watched = []

        if not limit.isdigit():
            limit = '10'

        try:
            if user_id:
                query = 'SELECT session_history.id, session_history.media_type, session_history.rating_key, session_history.parent_rating_key, ' \
                        'title, parent_title, grandparent_title, thumb, parent_thumb, grandparent_thumb, media_index, parent_media_index, ' \
                        'year, started, user ' \
                        'FROM session_history_metadata ' \
                        'JOIN session_history ON session_history_metadata.id = session_history.id ' \
                        'WHERE user_id = ? ' \
                        'GROUP BY (CASE WHEN session_history.media_type = "track" THEN session_history.parent_rating_key ' \
                        ' ELSE session_history.rating_key END) ' \
                        'ORDER BY started DESC LIMIT ?'
                result = monitor_db.select(query, args=[user_id, limit])
            elif user:
                query = 'SELECT session_history.id, session_history.media_type, session_history.rating_key, session_history.parent_rating_key, ' \
                        'title, parent_title, grandparent_title, thumb, parent_thumb, grandparent_thumb, media_index, parent_media_index, ' \
                        'year, started, user ' \
                        'FROM session_history_metadata ' \
                        'JOIN session_history ON session_history_metadata.id = session_history.id ' \
                        'WHERE user = ? ' \
                        'GROUP BY (CASE WHEN session_history.media_type = "track" THEN session_history.parent_rating_key ' \
                        ' ELSE session_history.rating_key END) ' \
                        'ORDER BY started DESC LIMIT ?'
                result = monitor_db.select(query, args=[user, limit])
            else:
                query = 'SELECT session_history.id, session_history.media_type, session_history.rating_key, session_history.parent_rating_key, ' \
                        'title, parent_title, grandparent_title, thumb, parent_thumb, grandparent_thumb, media_index, parent_media_index, ' \
                        'year, started, user ' \
                        'FROM session_history_metadata ' \
                        'JOIN session_history ON session_history_metadata.id = session_history.id ' \
                        'GROUP BY (CASE WHEN session_history.media_type = "track" THEN session_history.parent_rating_key ' \
                        ' ELSE session_history.rating_key END) ' \
                        'ORDER BY started DESC LIMIT ?'
                result = monitor_db.select(query, args=[limit])
        except:
            logger.warn("Unable to execute database query for get_recently_watched.")
            return None

        for row in result:
                if row['media_type'] == 'episode' and row['parent_thumb']:
                    thumb = row['parent_thumb']
                elif row['media_type'] == 'episode':
                    thumb = row['grandparent_thumb']
                else:
                    thumb = row['thumb']

                recent_output = {'row_id': row['id'],
                                 'type': row['media_type'],
                                 'rating_key': row['rating_key'],
                                 'title': row['title'],
                                 'parent_title': row['parent_title'],
                                 'grandparent_title': row['grandparent_title'],
                                 'thumb': thumb,
                                 'media_index': row['media_index'],
                                 'parent_media_index': row['parent_media_index'],
                                 'year': row['year'],
                                 'time': row['started'],
                                 'user': row['user']
                                 }
                recently_watched.append(recent_output)

        return recently_watched

    def get_metadata_details(self, row_id):
        monitor_db = database.MonitorDatabase()

        if row_id:
            query = 'SELECT session_history_metadata.rating_key, session_history_metadata.parent_rating_key, ' \
                    'session_history_metadata.grandparent_rating_key, session_history_metadata.title, ' \
                    'session_history_metadata.parent_title, session_history_metadata.grandparent_title, ' \
                    'session_history_metadata.full_title, library_sections.section_name, ' \
                    'session_history_metadata.media_index, session_history_metadata.parent_media_index, ' \
                    'session_history_metadata.library_id, session_history_metadata.thumb, ' \
                    'session_history_metadata.parent_thumb, session_history_metadata.grandparent_thumb, ' \
                    'session_history_metadata.art, session_history_metadata.media_type, session_history_metadata.year, ' \
                    'session_history_metadata.originally_available_at, session_history_metadata.added_at, ' \
                    'session_history_metadata.updated_at, session_history_metadata.last_viewed_at, ' \
                    'session_history_metadata.content_rating, session_history_metadata.summary, ' \
                    'session_history_metadata.tagline, session_history_metadata.rating, session_history_metadata.duration, ' \
                    'session_history_metadata.guid, session_history_metadata.directors, session_history_metadata.writers, ' \
                    'session_history_metadata.actors, session_history_metadata.genres, session_history_metadata.studio ' \
                    'FROM session_history_metadata ' \
                    'JOIN library_sections ON session_history_metadata.library_id = library_sections.section_id ' \
                    'WHERE session_history_metadata.id = ?'
            result = monitor_db.select(query=query, args=[row_id])
        else:
            result = []

        metadata = {}
        for item in result:
            directors = item['directors'].split(';') if item['directors'] else []
            writers = item['writers'].split(';') if item['writers'] else []
            actors = item['actors'].split(';') if item['actors'] else []
            genres = item['genres'].split(';') if item['genres'] else []

            metadata = {'media_type': item['media_type'],
                        'rating_key': item['rating_key'],
                        'parent_rating_key': item['parent_rating_key'],
                        'grandparent_rating_key': item['grandparent_rating_key'],
                        'grandparent_title': item['grandparent_title'],
                        'parent_media_index': item['parent_media_index'],
                        'parent_title': item['parent_title'],
                        'media_index': item['media_index'],
                        'studio': item['studio'],
                        'title': item['title'],
                        'content_rating': item['content_rating'],
                        'summary': item['summary'],
                        'tagline': item['tagline'],
                        'rating': item['rating'],
                        'duration': item['duration'],
                        'year': item['year'],
                        'thumb': item['thumb'],
                        'parent_thumb': item['parent_thumb'],
                        'grandparent_thumb': item['grandparent_thumb'],
                        'art': item['art'],
                        'originally_available_at': item['originally_available_at'],
                        'added_at': item['added_at'],
                        'updated_at': item['updated_at'],
                        'last_viewed_at': item['last_viewed_at'],
                        'guid': item['guid'],
                        'writers': writers,
                        'directors': directors,
                        'genres': genres,
                        'actors': actors,
                        'library_title': item['section_name'],
                        'library_id': item['library_id']
                        }

        return metadata

    def delete_session_history_rows(self, row_id=None):
        monitor_db = database.MonitorDatabase()

        if row_id.isdigit():
            logger.info(u"PlexPy DataFactory :: Deleting row id %s from the session history database." % row_id)
            session_history_del = \
                monitor_db.action('DELETE FROM session_history WHERE id = ?', [row_id])
            session_history_media_info_del = \
                monitor_db.action('DELETE FROM session_history_media_info WHERE id = ?', [row_id])
            session_history_metadata_del = \
                monitor_db.action('DELETE FROM session_history_metadata WHERE id = ?', [row_id])

            return 'Deleted rows %s.' % row_id
        else:
            return 'Unable to delete rows. Input row not valid.'

    def delete_all_user_history(self, user_id=None):
        monitor_db = database.MonitorDatabase()

        if user_id.isdigit():
            logger.info(u"PlexPy DataFactory :: Deleting all history for user id %s from database." % user_id)
            session_history_media_info_del = \
                monitor_db.action('DELETE FROM '
                                  'session_history_media_info '
                                  'WHERE session_history_media_info.id IN (SELECT session_history_media_info.id '
                                  'FROM session_history_media_info '
                                  'JOIN session_history ON session_history_media_info.id = session_history.id '
                                  'WHERE session_history.user_id = ?)', [user_id])
            session_history_metadata_del = \
                monitor_db.action('DELETE FROM '
                                  'session_history_metadata '
                                  'WHERE session_history_metadata.id IN (SELECT session_history_metadata.id '
                                  'FROM session_history_metadata '
                                  'JOIN session_history ON session_history_metadata.id = session_history.id '
                                  'WHERE session_history.user_id = ?)', [user_id])
            session_history_del = \
                monitor_db.action('DELETE FROM '
                                  'session_history '
                                  'WHERE session_history.user_id = ?', [user_id])

            return 'Deleted all items for user_id %s.' % user_id
        else:
            return 'Unable to delete items. Input user_id not valid.'

    def delete_user(self, user_id=None):
        monitor_db = database.MonitorDatabase()

        if user_id.isdigit():
            self.delete_all_user_history(user_id)
            logger.info(u"PlexPy DataFactory :: Deleting user with id %s from database." % user_id)
            monitor_db.action('UPDATE users SET deleted_user = 1 WHERE user_id = ?', [user_id])
            monitor_db.action('UPDATE users SET keep_history = 0 WHERE user_id = ?', [user_id])
            monitor_db.action('UPDATE users SET do_notify = 0 WHERE user_id = ?', [user_id])

            return 'Deleted user with id %s.' % user_id
        else:
            return 'Unable to delete user. Input user_id not valid.'

    def undelete_user(self, user_id=None, username=None):
        monitor_db = database.MonitorDatabase()

        if user_id and user_id.isdigit():
            logger.info(u"PlexPy DataFactory :: Re-adding user with id %s to database." % user_id)
            monitor_db.action('UPDATE users SET deleted_user = 0 WHERE user_id = ?', [user_id])
            monitor_db.action('UPDATE users SET keep_history = 1 WHERE user_id = ?', [user_id])
            monitor_db.action('UPDATE users SET do_notify = 1 WHERE user_id = ?', [user_id])

            return 'Re-added user with id %s.' % user_id
        elif username:
            logger.info(u"PlexPy DataFactory :: Re-adding user with username %s to database." % username)
            monitor_db.action('UPDATE users SET deleted_user = 0 WHERE username = ?', [username])
            monitor_db.action('UPDATE users SET keep_history = 1 WHERE username = ?', [username])
            monitor_db.action('UPDATE users SET do_notify = 1 WHERE username = ?', [username])

            return 'Re-added user with username %s.' % username
        else:
            return 'Unable to re-add user. Input user_id or username not valid.'

    def get_search_query(self, rating_key=''):
        monitor_db = database.MonitorDatabase()

        if rating_key:
            query = 'SELECT rating_key, parent_rating_key, grandparent_rating_key, title, parent_title, grandparent_title, ' \
                    'media_index, parent_media_index, year, media_type ' \
                    'FROM session_history_metadata ' \
                    'WHERE rating_key = ? ' \
                    'OR parent_rating_key = ? ' \
                    'OR grandparent_rating_key = ? ' \
                    'LIMIT 1'
            result = monitor_db.select(query=query, args=[rating_key, rating_key, rating_key])
        else:
            result = []

        query = {}
        query_string = None
        media_type = None

        for item in result:
            title = item['title']
            parent_title = item['parent_title']
            grandparent_title = item['grandparent_title']
            media_index = item['media_index']
            parent_media_index = item['parent_media_index']
            year = item['year']

            if str(item['rating_key']) == rating_key:
                query_string = item['title']
                media_type = item['media_type']

            elif str(item['parent_rating_key']) == rating_key:
                if item['media_type'] == 'episode':
                    query_string = item['grandparent_title']
                    media_type = 'season'
                elif item['media_type'] == 'track':
                    query_string = item['parent_title']
                    media_type = 'album'

            elif str(item['grandparent_rating_key']) == rating_key:
                if item['media_type'] == 'episode':
                    query_string = item['grandparent_title']
                    media_type = 'show'
                elif item['media_type'] == 'track':
                    query_string = item['grandparent_title']
                    media_type = 'artist'

        if query_string and media_type:
            query = {'query_string': query_string,
                     'title': title,
                     'parent_title': parent_title,
                     'grandparent_title': grandparent_title,
                     'media_index': media_index,
                     'parent_media_index': parent_media_index,
                     'year': year,
                     'media_type': media_type,
                     'rating_key': rating_key
                     }
        else:
            return None

        return query

    def get_rating_keys_list(self, rating_key='', media_type=''):
        monitor_db = database.MonitorDatabase()

        if media_type == 'movie':
            key_list = {0: {'rating_key': int(rating_key)}}
            return key_list

        if media_type == 'artist' or media_type == 'album' or media_type == 'track':
            match_type = 'title'
        else:
            match_type = 'index'

        # Get the grandparent rating key
        try:
            query = 'SELECT rating_key, parent_rating_key, grandparent_rating_key ' \
                    'FROM session_history_metadata ' \
                    'WHERE rating_key = ? ' \
                    'OR parent_rating_key = ? ' \
                    'OR grandparent_rating_key = ? ' \
                    'LIMIT 1'
            result = monitor_db.select(query=query, args=[rating_key, rating_key, rating_key])

            grandparent_rating_key = result[0]['grandparent_rating_key']

        except:
            logger.warn("Unable to execute database query for get_rating_keys_list.")
            return {}

        query = 'SELECT rating_key, parent_rating_key, grandparent_rating_key, title, parent_title, grandparent_title, ' \
                'media_index, parent_media_index ' \
                'FROM session_history_metadata ' \
                'WHERE {0} = ? ' \
                'GROUP BY {1} '

        # get grandparent_rating_keys
        grandparents = {}
        result = monitor_db.select(query=query.format('grandparent_rating_key', 'grandparent_rating_key'),
                                   args=[grandparent_rating_key])
        for item in result:
            # get parent_rating_keys
            parents = {}
            result = monitor_db.select(query=query.format('grandparent_rating_key', 'parent_rating_key'),
                                       args=[item['grandparent_rating_key']])
            for item in result:
                # get rating_keys
                children = {}
                result = monitor_db.select(query=query.format('parent_rating_key', 'rating_key'),
                                           args=[item['parent_rating_key']])
                for item in result:
                    key = item['media_index']
                    children.update({key: {'rating_key': item['rating_key']}})

                key = item['parent_media_index'] if match_type == 'index' else item['parent_title']
                parents.update({key:
                                {'rating_key': item['parent_rating_key'],
                                 'children': children}
                                })

            key = 0 if match_type == 'index' else item['grandparent_title']
            grandparents.update({key:
                                 {'rating_key': item['grandparent_rating_key'],
                                  'children': parents}
                                 })

        key_list = grandparents

        return key_list

    def update_metadata(self, old_key_list='', new_key_list='', media_type=''):
        from plexpy import pmsconnect
        pms_connect = pmsconnect.PmsConnect()
        monitor_db = database.MonitorDatabase()

        # function to map rating keys pairs
        def get_pairs(old, new):
            pairs = {}
            for k, v in old.iteritems():
                if k in new:
                    if v['rating_key'] != new[k]['rating_key']:
                        pairs.update({v['rating_key']: new[k]['rating_key']})
                    if 'children' in old[k]:
                        pairs.update(get_pairs(old[k]['children'], new[k]['children']))

            return pairs

        # map rating keys pairs
        mapping = {}
        if old_key_list and new_key_list:
            mapping = get_pairs(old_key_list, new_key_list)

        if mapping:
            logger.info(u"PlexPy DataFactory :: Updating metadata in the database.")
            for old_key, new_key in mapping.iteritems():
                metadata = pms_connect.get_metadata_details(new_key)

                if metadata:
                    metadata = metadata['metadata']
                    if metadata['media_type'] == 'show' or metadata['media_type'] == 'artist':
                        # check grandparent_rating_key (2 tables)
                        monitor_db.action('UPDATE session_history SET grandparent_rating_key = ? WHERE grandparent_rating_key = ?', 
                                          [new_key, old_key])
                        monitor_db.action('UPDATE session_history_metadata SET grandparent_rating_key = ? WHERE grandparent_rating_key = ?', 
                                          [new_key, old_key])
                    elif metadata['media_type'] == 'season' or metadata['media_type'] == 'album':
                        # check parent_rating_key (2 tables)
                        monitor_db.action('UPDATE session_history SET parent_rating_key = ? WHERE parent_rating_key = ?', 
                                          [new_key, old_key])
                        monitor_db.action('UPDATE session_history_metadata SET parent_rating_key = ? WHERE parent_rating_key = ?', 
                                          [new_key, old_key])
                    else:
                        # check rating_key (2 tables)
                        monitor_db.action('UPDATE session_history SET rating_key = ? WHERE rating_key = ?', 
                                          [new_key, old_key])
                        monitor_db.action('UPDATE session_history_media_info SET rating_key = ? WHERE rating_key = ?', 
                                          [new_key, old_key])

                        # update session_history_metadata table
                        self.update_metadata_details(old_key, new_key, metadata)

            return 'Updated metadata in database.'
        else:
            return 'Unable to update metadata in database. No changes were made.'
        # for debugging
        #return mapping

    def update_metadata_details(self, old_rating_key='', new_rating_key='', metadata=None):

        if metadata:
            # Create full_title
            if metadata['media_type'] == 'episode' or metadata['media_type'] == 'track':
                full_title = '%s - %s' % (metadata['grandparent_title'], metadata['title'])
            else:
                full_title = metadata['title']

            directors = ";".join(metadata['directors'])
            writers = ";".join(metadata['writers'])
            actors = ";".join(metadata['actors'])
            genres = ";".join(metadata['genres'])

            logger.info(u"PlexPy DataFactory :: Updating metadata in the database for rating key: %s." % new_rating_key)
            monitor_db = database.MonitorDatabase()

            # Update the session_history_metadata table
            query = 'UPDATE session_history_metadata SET rating_key = ?, parent_rating_key = ?, ' \
                    'grandparent_rating_key = ?, title = ?, parent_title = ?, grandparent_title = ?, full_title = ?, ' \
                    'media_index = ?, parent_media_index = ?, library_id = ?, thumb = ?, parent_thumb = ?, ' \
                    'grandparent_thumb = ?, art = ?, media_type = ?, year = ?, originally_available_at = ?, ' \
                    'added_at = ?, updated_at = ?, last_viewed_at = ?, content_rating = ?, summary = ?, ' \
                    'tagline = ?, rating = ?, duration = ?, guid = ?, directors = ?, writers = ?, actors = ?, ' \
                    'genres = ?, studio = ? ' \
                    'WHERE rating_key = ?'

            args = [metadata['rating_key'], metadata['parent_rating_key'], metadata['grandparent_rating_key'],
                    metadata['title'], metadata['parent_title'], metadata['grandparent_title'], full_title,
                    metadata['media_index'], metadata['parent_media_index'], metadata['library_id'], metadata['thumb'],
                    metadata['parent_thumb'], metadata['grandparent_thumb'], metadata['art'], metadata['media_type'],
                    metadata['year'], metadata['originally_available_at'], metadata['added_at'], metadata['updated_at'],
                    metadata['last_viewed_at'], metadata['content_rating'], metadata['summary'], metadata['tagline'], 
                    metadata['rating'], metadata['duration'], metadata['guid'], directors, writers, actors, genres,
                    metadata['studio'],
                    old_rating_key]

            monitor_db.action(query=query, args=args)

    def update_library_ids(self):
        from plexpy import pmsconnect

        pms_connect = pmsconnect.PmsConnect()
        monitor_db = database.MonitorDatabase()

        try:
            query = 'SELECT id, rating_key FROM session_history_metadata WHERE library_id IS NULL'
            result = monitor_db.select(query=query)
        except:
            logger.warn("Unable to execute database query for update_library_id.")
            return None

        for item in result:
            id = item[0]
            rating_key = item[1]

            result = pms_connect.get_metadata_details(rating_key=rating_key)

            if result:
                metadata = result['metadata']

                section_keys = {'id': id}
                section_values = {'library_id': metadata['library_id']}

                monitor_db.upsert('session_history_metadata', key_dict=section_keys, value_dict=section_values)
            else:
                continue

        return True

    def update_library_sections(self):
        from plexpy import pmsconnect

        pms_connect = pmsconnect.PmsConnect()
        library_sections = pms_connect.get_server_children()

        if library_sections:
            if library_sections['libraries_count'] != '0':
                monitor_db = database.MonitorDatabase()

                for section in library_sections['libraries_list']:
                    section_keys = {'section_id': section['key']}
                    section_values = {'section_id': section['key'],
                                      'section_name': section['title'],
                                      'section_type': section['type']}

                    monitor_db.upsert('library_sections', key_dict=section_keys, value_dict=section_values)

        return True

    def get_session_ip(self, session_key=''):
        monitor_db = database.MonitorDatabase()

        if session_key:
            query = 'SELECT ip_address FROM sessions WHERE session_key = %d' % int(session_key)
            result = monitor_db.select(query)
        else:
            return None

        ip_address = 'N/A'

        for item in result:
            ip_address = item[0]

        return ip_address