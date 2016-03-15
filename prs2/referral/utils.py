# Django imports
from django.db.models import get_model, Q
from django.db.models.base import ModelBase
from django.utils.safestring import mark_safe
from django.contrib import admin
from django.contrib import messages
import re
from django.utils.encoding import smart_str
from datetime import datetime
import json


def is_model_or_string(model):
    '''
    This function checks if we passed in a Model, or the name of a model as a string
    (case insensitive). The string may also be plural to some extent (i.e. ending with "s").
    If we passed in a string, return the named Model instead using get_model().

    Business rules::
        No restrictions.

    Example::

        from referral.util import is_model_or_string
        is_model_or_string('region')
        is_model_or_string(Region)

    >>> from referral.models import Region
    >>> from django.db.models.base import ModelBase
    >>> from referral.util import is_model_or_string
    >>> isinstance(is_model_or_string('region'), ModelBase)
    True
    >>> isinstance(is_model_or_string(Region), ModelBase)
    True

    '''
    if not isinstance(model, ModelBase):
        # Hack: if the last character is "s", remove it before calling get_model
        x = len(model) - 1
        if model[x] == 's':
            model = model[0:x]
        try:
            model = get_model('referral', model)
        except LookupError:
            model = None
    return model


def smart_truncate(content, length=100, suffix='....(more)'):
    """Small function to truncate a string in a sensible way, sourced from:
    http://stackoverflow.com/questions/250357/smart-truncate-in-python
    """
    content = smart_str(content)
    if len(content) <= length:
        return content
    else:
        return ' '.join(content[:length + 1].split(' ')[0:-1]) + suffix


REPLACEMENTS = dict([('&nbsp;', ' '),
                     ('&lt;', '<'),
                     ('&gt;', '>'),
                     (' class="MsoNormal"', ''),
                     ('<span lang="EN-AU">', ''),
                     ('<span>', ''),
                     ('</span>', '')])


def replacer(m):
    return REPLACEMENTS[m.group(0)]


def dewordify_text(x):
    '''
    Function to strip some of the crufty HTML that results from copy-pasting from Word into the
    RTF text fields in this application.
    Source:
            http://stackoverflow.com/questions/1175540/iterative-find-replace-from-a-list-of-tuples-in-python
    '''
    if x:
        r = re.compile('|'.join(REPLACEMENTS.keys()))
        return r.sub(replacer, x)
    else:
        return ''


def breadcrumbs_li(links):
    """Returns HTML: an unordered list of URLs (no surrounding <ul> tags).
    ``links`` should be a iterable of tuples (URL, text).
    """
    crumbs = ''
    li_str = '<li><a href="{}">{}</a></li>'
    li_str_last = '<li class="active"><span>{}</span></li>'
    # Iterate over the list, except for the last item.
    if len(links) > 1:
        for i in links[:-1]:
            crumbs += li_str.format(i[0], i[1])
    # Add the last item.
    crumbs += li_str_last.format(links[-1][1])
    return crumbs


def get_query(query_string, search_fields):
    """Returns a query which is a combination of Q objects. That combination
    aims to search keywords within a model by testing the given search fields.

    Splits the query string into individual keywords, getting rid of unecessary
    spaces and grouping quoted words together.
    """
    findterms = re.compile(r'"([^"]+)"|(\S+)').findall
    normspace = re.compile(r'\s{2,}').sub
    query = None  # Query to search for every search term
    terms = [normspace(' ', (t[0] or t[1]).strip()) for t in findterms(query_string)]
    for term in terms:
        or_query = None  # Query to search for a given term in each field
        for field_name in search_fields:
            q = Q(**{"%s__icontains" % field_name: term})
            if or_query is None:
                or_query = q
            else:
                or_query = or_query | q
        if query is None:
            query = or_query
        else:
            query = query & or_query
    return query


def as_row_subtract_referral_cell(html_row):
    """Function to take some HTML of a table row and then remove the cell
    containing the Referral ID (we don't need to display this on the referral details page).
    """
    # Use regex to remove the <TD> tag of class "referral-id-cell".
    html_row = re.sub(r'<td class="referral-id-cell">.+</td>', r'', html_row)
    return mark_safe(html_row)


def user_referral_history(user, referral):
    # Retrieve user profile (create it if it doesn't exist)
    try:
        profile = user.get_profile()
    except:
        profile = user.userprofile
    # If the user has no history, create an empty list
    if not profile.referral_history:
        ref_history = []
    else:
        try:
            # Deserialise the list of lists from the user profile
            ref_history = json.loads(profile.referral_history)
        except:
            # If that failed, assume that the user still has "old style" history in their profile.
            ref_history = profile.referral_history.split(',')
    # Edge-case: single-ref history profiles only.
    if isinstance(ref_history, int):
        ref = ref_history
        ref_history = []
        ref_history.append([ref, datetime.strftime(datetime.today(), '%d-%m-%Y')])
    # We're going to replace the existing list with a new one.
    new_ref_history = []
    # Iterate through the list; it's either a list of unicode strings (old-style)
    # or a list of lists (new-style).
    for i in ref_history:
        # Firstly if the item is a unicode-format integer, convert that to a list.
        if isinstance(i, unicode):
            i = [int(i), datetime.strftime(datetime.today(), '%d-%m-%Y')]
        # If the referral that was passed in exists in the current list, pass (don't append it).
        if referral.id == i[0]:
            pass
        else:
            new_ref_history.append(i)
    # Add the passed-in referral to the end of the new list.
    new_ref_history.append([referral.id, datetime.strftime(datetime.today(), '%d-%m-%Y')])
    # History can be a maximum of 20 referrals; slice the new list accordingly.
    if len(new_ref_history) > 20:
        new_ref_history = new_ref_history[-20:]
    # Save the updated user profile; serialise the new list of lists.
    profile.referral_history = json.dumps(new_ref_history)
    profile.save()


def user_task_history(user, task, comment=None):
    profile = user.userprofile
    if not profile.task_history:
        task_history = []
    else:
        task_history = json.loads(profile.task_history)
    task_history.append([task.pk, datetime.strftime(datetime.today(), '%d-%m-%Y'), comment])
    profile.task_history = json.dumps(task_history)
    profile.save()


def filter_queryset(request, model, queryset):
    '''
    Function to dynamically filter a model queryset, based upon the search_fields defined in
    admin.py for that model. If search_fields is not defined, the queryset is returned unchanged.
    '''
    search_string = request.GET['q']
    # Replace single-quotes with double-quotes
    search_string = search_string.replace("'", r'"')
    if admin.site._registry[model].search_fields:
        search_fields = admin.site._registry[model].search_fields
        entry_query = get_query(search_string, search_fields)
        queryset = queryset.filter(entry_query)
    return queryset, search_string


def is_prs_user(request):
    if not 'PRS user' in [group.name for group in  request.user.groups.all()]:
        return False
    return True


def is_prs_power_user(request):
    if not 'PRS power user' in [group.name for group in  request.user.groups.all()]:
        return False
    return True


def is_superuser(request):
    return request.user.is_superuser


def prs_user(request):
    return is_prs_user(request) or is_prs_power_user(request) or is_superuser(request)