import argparse
import datetime
import json
import sys
import time

import colorama
import requests

session = requests.Session()


def get_changes(auth_creds, query):
    auth = requests.auth.HTTPDigestAuth(*auth_creds)
    result = session.get('https://review.openstack.org/a/changes/',
                         params='q=%s&'
                                'pp=0&'
                                'o=DETAILED_ACCOUNTS&'
                                'o=DETAILED_LABELS&'
                                'n=22' % query,
                         auth=auth,
                         timeout=30)
    result.raise_for_status()
    data = ''.join(x for x in result.iter_content(1024, decode_unicode=True))
    result = data[5:]
    changes = json.loads(result)
    return changes


def green_line(line):
    return colorama.Fore.GREEN + line + colorama.Fore.RESET


def yellow_line(line):
    return colorama.Fore.YELLOW + line + colorama.Fore.RESET


def red_line(line):
    return colorama.Fore.RED + line + colorama.Fore.RESET


def cyan_line(line):
    return colorama.Fore.CYAN + line + colorama.Fore.RESET


def red_background_line(line):
    return (colorama.Back.RED + colorama.Style.BRIGHT + line +
            colorama.Style.RESET_ALL + colorama.Back.RESET)

def dim_line(line):
    return colorama.Style.DIM + line + colorama.Style.RESET_ALL


def _reset_terminal():
    sys.stderr.write("\x1b[2J\x1b[H")


def error(msg):
    _reset_terminal()
    print(red_background_line(msg))

def format_time(secs):
    if secs < 60:
        return "%is" % secs
    elif secs < 3600:
        return "%im" % (secs / 60)
    elif secs < 3600 * 24:
        return "%ih%im" % ((secs / 3600),
                           (secs % 3600) / 60)
    else:
        return "%id%ih" % ((secs / (3600 * 24)),
                           (secs % (3600 * 24)) / (3600))



def vote_to_colored_char(vote):
    if vote > 0:
        vote = green_line(str(vote))
    elif vote == 0:
        vote = '_'
    else:
        vote = red_line(str(abs(vote)))
    return vote


def build_change_line(change):
    review_votes = [vote.get('value', 0) for vote in change['labels'].get(
        'Code-Review', {}).get('all', [])]
    if review_votes:
        if abs(min(review_votes)) >= abs(max(review_votes)):
            review_vote = min(review_votes)
        else:
            review_vote = max(review_votes)
    else:
        review_vote = 0

    review_vote = vote_to_colored_char(review_vote)
    verified_votes = change['labels'].get('Verified', {}).get('all', []) 
    jenkins = list(filter(lambda vote: vote.get('username') == 'zuul',
                          verified_votes))
    if jenkins:
        jenkins_vote = jenkins[0].get('value', 0)
    else:
        jenkins_vote = 0

    jenkins_vote = vote_to_colored_char(jenkins_vote)

    workflow_vote = max([0] + [vote.get('value', 0) for vote in change['labels'].get(
        'Workflow', {}).get('all', [])])
    workflow_vote = vote_to_colored_char(workflow_vote)

    updated_ago = (time.time() -
                   (datetime.datetime.strptime(
                        change['updated'][0:-3],
                        "%Y-%m-%d %H:%M:%S.%f") - datetime.datetime(1970, 1, 1)).total_seconds())
    updated_ago = format_time(updated_ago)

    mergeable = '_' if change.get('mergeable', True) else red_line('M')

    number = str(change['_number'])

    if change['status'] == 'MERGED':
        subject = green_line(change['subject'])
        number = green_line(number)
    elif change['status'] == 'ABANDONED':
        subject = dim_line(change['subject'])
    else:
        subject = change['subject']

    line = ''.join([number, ' ', mergeable, review_vote, jenkins_vote,
                    workflow_vote, ' ', subject, ' - ', updated_ago,
                    ' ago'])
    return line

def do_dashboard(auth_creds, query):
    try:
        changes = get_changes(auth_creds, query)
    except Exception as e:
        error('Failed to get changes from Gerrit: %s' % e)
        return

    _reset_terminal()
    print('Salmon review dashboard - %s' % time.asctime())
    print('id     MRVW subject                            - updated at')
    for change in changes:
        print(build_change_line(change))


def parse_args():
    argparser = argparse.ArgumentParser(
        description="Show the result of the result of a Gerrit query.")
    argparser.add_argument('-u', '--user', help='Gerrit username')
    argparser.add_argument('-P', '--passwd', help='Gerrit password')
    argparser.add_argument('-r', '--refresh', help='Refresh in seconds',
                           default=0, type=int)
    argparser.add_argument('-q', '--query', help='The Gerrit query to show')
    return argparser.parse_args()


def main():
    opts = parse_args()
    auth_creds = (opts.user, opts.passwd)

    while True:
        try:
            do_dashboard(auth_creds, opts.query)
            if not opts.refresh:
                break
            time.sleep(opts.refresh)
        except KeyboardInterrupt:
            break


if __name__ == '__main__':
    main()
