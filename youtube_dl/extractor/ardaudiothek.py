# coding: utf-8
from __future__ import unicode_literals

import re

try:
    from urllib.parse import unquote as _unquote_compat
except ImportError:
    from urllib import unquote

    def _unquote_compat(str):
        return unquote(str.encode('utf-8')).decode('utf-8')

from .common import InfoExtractor
from ..utils import (
    compat_str,
    ExtractorError,
    int_or_none,
    parse_duration,
    str_or_none,
    try_get,
    unified_strdate,
    unified_timestamp,
)


class ARDAudiothekBaseIE(InfoExtractor): 
    """
    InfoExtractor for the ARD Audiothek at <https://ardaudiothek.de>

    The ARD Audiothek exposes a GraphQL API at
    <https://api.ardaudiothek.de/graphql/>.

    The following routes from the web interface at <https://ardaudiothek.de>
    contain content users might want to download with youtube-dl:

    /episode:  As the name suggests anything below here is a single episode
               that will result in a single audio file.  
               In the GraphQL API this is called an *item*.

    /sendung:  Below here we will find is a collection of episodes, we could
               name this podcast or show, internally it is called a program
               set. Under youtube-dl aspects, this is a playlist, resulting in
               several audio files. 
               In the GraphQL API, this is called a *programSet* or *show*.

    /sammlung: This is a collection of episodes with a common theme. Again, for
               us this is merely a playlist.
               In the GraphQL API, this is called an *editorialCollection*.

    /suche:    This is a search result. Since the site is very generously
               returning hundreds of results even for very specific search 
               strings, it only makes sense to use such a route with 
               ``--max-downloads`` or ``--get-url``.
               In the GraphQL API, this corresponds to *search*.  
    """

    def _extract_episode(self, ep_data):
        res = {
            'id': try_get(ep_data, lambda x: x['id'], compat_str),
            'title': try_get(ep_data, lambda x: x['title'], compat_str),
            'description': try_get(ep_data, lambda x: x['description'], compat_str)
            } 

        res['url'] = try_get(ep_data, [
            lambda x: x['audios'][0]['url'],
            lambda x: x['audios'][0]['downloadUrl'], 
        ], compat_str)
        if not res['url']:
            raise ExtractorError(msg='Could not find a URL to download',
                                 expected=True)

        res['duration'] = try_get(ep_data, lambda x: x['duration'], int)
        res['upload_date'] = unified_strdate(
            try_get(ep_data, lambda x: x['publishDate'], compat_str))

        res['is_live'] = False

        res['thumbnail'] = try_get(ep_data, lambda x: x['image']['url1X1'].format(width=320), compat_str) 

        res['channel'] = try_get(ep_data, lambda x: x['programSet']['publicationService']['organizationName'], compat_str) 
        res['series'] = try_get(ep_data, lambda x: x['programSet']['title'], compat_str) 
        res['categories'] = try_get(ep_data, lambda x: x['programSet']['publicationService']['genre'], compat_str) 

        return res

    def _extract_sammlung_sendung(self, playlist_id, playlist_type):
        api_url = 'https://api.ardaudiothek.de/graphql' 
        result_data = self._download_json(api_url, playlist_id, 
            headers={'Accept': 'application/json'}, 
            query={'query':'''{%s(id:"%s"){id,title,numberOfElements,items{nodes{id,title,audios{url,downloadUrl},image{url1X1},duration,publishDate,description:synopsis,programSet{title,publicationService{organizationName,genre}}}}}}''' % (playlist_type , playlist_id)}) 
        entries = try_get(result_data, lambda x: x['data'][playlist_type]['items']['nodes'], list)
        if not entries:
            raise ExtractorError(msg="Could not find any playlist data",
                                 expected=True)
        res = {
            'id': try_get(result_data, lambda x: x['data'][playlist_type]['id'], compat_str),
            'title': try_get(result_data, lambda x: x['data'][playlist_type]['title'], compat_str)
            }
        res['_type'] = 'playlist'
        res['entries'] = list()
        for entry in entries:
          try:
            res['entries'].append(self._extract_episode(entry))
          except ExtractorError:
            self.report_warning("Could not find download url for entry %s. Might be a duplicate/garbage entry." % entry["id"], video_id=entry["id"])
        return res 

class ARDAudiothekEpisodeIE(ARDAudiothekBaseIE):
    """
    InfoExtractor for route "/episode"

    """
    _VALID_URL = r'https?://(?:www\.)?ardaudiothek\.de/episode/(?:[^/]+)/(?:[^/]+)/(?:[^/]+)/(?P<id>[0-9]+)(?:/.*)?'
    _TESTS = [{
        'url': 'https://www.ardaudiothek.de/episode/die-profis/philosophie-meditation-und-die-aufloesung-des-ichs/radioeins/10525879/',
        'md5': '3f9f44536b60c0207d1cce45765f6cb0',
        'info_dict': {
            'id': '10525879',
            'ext': 'mp3',
            'title': 'Philosophie - Meditation und die Auflösung des Ichs',
            'description': r're:^Meditation hilft gegen Stress.*',
            'thumbnail': compat_str,
            'timestamp': 1653118800,
            'upload_date': '20220521',
        }
    }
    ]

    def _real_extract(self, url):
        episode_id = self._match_id(url)

        api_url = 'https://api.ardaudiothek.de/graphql'
        result_data = self._download_json(api_url, episode_id, 
          headers={'Accept': 'application/json'}, 
          query={'query':'''query{item(id:"%s"){id,title,audios{url,downloadUrl},image{url1X1},duration,publishDate,description:synopsis,programSet{title,publicationService{organizationName,genre}}}}''' % episode_id})
        ep_data = try_get(result_data, lambda x: x['data']['item'], dict)

        if not ep_data:
            raise ExtractorError(msg="Could not find any episode data",
                                 expected=True)

        return self._extract_episode(ep_data)

class ARDAudiothekSammlungIE(ARDAudiothekBaseIE):
    """
    InfoExtractor for route "/sammlung"

    Note that this is in principal identical with route "sendung".
    We can use the same real_extract with a slightly different GraphQL query.

    """
    _VALID_URL = r'https?://(?:www\.)?ardaudiothek\.de/sammlung/(?:[^/]+)/(?P<id>[0-9]+)(?:/.*)?' 
    _TESTS = [{
        'url': 'https://www.ardaudiothek.de/sammlung/was-gibt-s-zu-essen-mythen-und-fakten-zur-guten-ernaehrung/56081830/',
        'info_dict': {
            'id': '56081830',
            'title': "Was gibt's zu essen? Mythen und Fakten zur guten Ernährung"
        },
        'playlist_mincount': 3,
    }]

    def _real_extract(self, url):
        playlist_id = self._match_id(url)
        playlist_type = "editorialCollection"
        return self._extract_sammlung_sendung(playlist_id, playlist_type)
            
class ARDAudiothekSendungIE(ARDAudiothekBaseIE):
    """
    InfoExtractor for route "/sendung"

    Note that this is in principal identical with route "sammlung".
    We can use the same real_extract with a slightly different GraphQL query.

    """
    _VALID_URL = r'https?://(?:www\.)?ardaudiothek\.de/sendung/(?:[^/]+)/(?P<id>[0-9]+)(?:/.*)?' 
    _TESTS = [{
        'url': 'https://www.ardaudiothek.de/sendung/korridore-mystery-horror-serie/12187357/',
        'info_dict': {
            'id': '12187357',
            'title': r're:^Korridore - Mystery-Horror-Serie',
        },
        'playlist_mincount': 3,
    }]

    def _real_extract(self, url):
        playlist_id = self._match_id(url)
        playlist_type = "programSet"
        return self._extract_sammlung_sendung(playlist_id, playlist_type)
 
class ARDAudiothekSucheIE(ARDAudiothekBaseIE):
    """
    InfoExtractor for route "/search"

    We are searching only for episodes. The web interface searches for
    collections and program sets, but the user can grab these much better with
    the "/sammlung" and "/sendung" routes.

    """ 
    _VALID_URL = r'https?://(?:www\.)?ardaudiothek\.de/suche/(?P<id>.+)/'
    _TESTS = [{
    }]

    def _real_extract(self, url):
        search_str = self._match_id(url)
        api_url = 'https://api.ardaudiothek.de/graphql' 
        result_data = self._download_json(api_url, None, 
            headers={'Accept': 'application/json'}, 
            query={'query':'''{search(query:"%s"){items{totalCount nodes{id,title,audios{url,downloadUrl},image{url1X1},duration,publishDate,description:synopsis,programSet{title,publicationService{organizationName,genre}}}}}}''' % (search_str)}) 
        entries = try_get(result_data, lambda x: x['data']['search']['items']['nodes'], list)
        if not entries:
            raise ExtractorError(msg="Could not find any search results",
                                 expected=True)
        res = {
            'id': None,
            'title': search_str
            }
        res['_type'] = 'playlist'
        res['entries'] = list()
        for entry in entries:
          try:
            res['entries'].append(self._extract_episode(entry))
          except ExtractorError:
            self.report_warning("Could not find download url for entry %s. Might be a duplicate/garbage entry." % entry["id"], video_id=entry["id"])
        return res 

