#!/usr/bin/env python

import sys, csv, datetime

# this script requires the following input files which for privacy
# reasons are not included in the git repo:
# contributors.csv  friends.csv  <bankaccountexport>.csv  latest-transactions.csv

# bugs:
#  - people who paid 1 year in advance before the opening of the
#    bank account are listed as inactive, while their contribs are
#    included in the budget.

# todo
# possibly send out automated emails with the stats to all contributors
#          send out automated emails to those who should

# costs = {'internet': 47.19, 'slak':  287, 'bank': 12.09} # 1st 6 months discount, no insurance
# costs = {'internet': 47.19, 'slak':  357, 'bank': 12.09} # no discount, no insurance
costs = {
    'internet': 47.19,
    'slak':  357,
    'bank': 12.09,  # based on triodos for 3 months, divided by 3
    'insurance': 72.6 / 12,
}

balance = 0
friends_fee = 7.5
friends_fname = 'friends.csv'
contributors_fname = 'contributors.csv'

# contributors.csv is a hand-maintained tsv file with the following fields
# nick, pledge, email, bank account1, ... bank account N
def load_contributors(cf): # regular contributors
    res = {}
    res2= {}
    with open(cf,'r') as fd:
        for line in fd.readlines():
            r = line.strip().split('\t')
            rec = {'pledge': float(r[1]),
                   'name': r[0].decode('utf8'),
                   'email': r[2],
                   'balance': 0,
                   'active': False}
            for id in r[3:]:
                res[id] = rec
                tmp = id.split()
                if len(tmp)>1: # skip fake acct ids
                    res2[tmp[1]] = id
    return res, res2

# friends.csv is a hand-maintained tsv file with the following fields
# name, bank account1, ... bank account N
def load_friends(ff): # people using our internet
    res = {}
    res2= {}
    with open(ff,'r') as fd:
        for line in fd.readlines():
            r = line.strip().split('\t')
            for id in r[1:]:
                res[id] = {
                    'name': r[0].decode('utf8'),
                    'balance': 0
                }
                tmp = id.split()
                if len(tmp)>1: # skip fake acct ids
                    res2[tmp[1]] = id
    return res, res2

# this is a csv export from triodos, no changes
def load_bankstatement(sf):
    res = []
    with open(sf, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        res = [{ 'date': datetime.datetime.strptime(row[0], "%d-%m-%Y"),
                 'value': float(row[2].replace(',','.')) * (-1 if row[3] == 'Debet' else 1),
                 'name': row[4],
                 'account': row[5],
                 'comment': row[7]}
               for row in reader]
        return res

# this is the copy/paste of the transactions of the running month, with each record joined into 1 line
# (originally the html copy paste puts each record into 3 lines)
def load_latest(lf):
    res = []
    with open(lf, 'rb') as fd:
        for line in fd.readlines():
            toks = line.strip().split()
            val = float(toks[-1].replace(",","."))
            if val<=0: continue
            rec = {
                'date': datetime.datetime.strptime(toks[0], "%d-%m-%Y"),
                'account': ''.join(toks[1:6]),
                'value': val,
                'text': ' '.join(toks[6:-1])
            }
            res.append(rec)
    return res

def contributor_stats(contributors, costs):
    print >>sys.stderr, "[i] contributor stats"
    print >>sys.stderr, "\ttotal contributors:\t %d" % len(contributors)
    avg = (float(costs) / len(contributors))
    print >>sys.stderr, "\tavg needed:\t\t %.02f" % avg
    # adjust costs by people pledged less than avg
    under = [x['pledge'] for x in contributors.values() if x['pledge']<avg]
    print >>sys.stderr, "\tcontributors under avg:\t %s" % under
    costs -= sum(under)
    contrib = (float(costs) / (len(contributors) - len(under)))
    print >>sys.stderr, "\tadjusted avg:\t\t %.02f" % contrib
    return contrib

def get_non_paying_members(contributors, share):
    non_paying_members = []
    seen = set()
    for c in contributors.values():
        if not c['active']: continue
        # some members have multiple bank accounts, they would be checked multiple times
        if c['name'] in seen: continue
        seen.add(c['name'])

        if c['pledge'] < share:
            contrib = c['pledge']
        else:
            contrib = share

        if c['balance']<contrib:
            non_paying_members.append(c['name'])
        else:
            c['balance']-=contrib
    return ', '.join(non_paying_members)

def get_non_paying_friends(friends):
    non_paying_friends = []
    for f in friends.values():
        if f['balance']<friends_fee and f['name'] not in non_paying_friends:
            non_paying_friends.append(f['name'])
        else:
            f['balance']-=friends_fee
    return non_paying_friends

# this is the main "datamining" function, using all available information.
def bankstatement_stats(statments, balance, contributors, friends, share, latest):
    print >>sys.stderr, "[i] stats for bank balance"
    print >>sys.stderr, "           date change opening contrib suppliers supporters non-paying members & friends"
    month = None
    members = []    # contributors
    supporters = [] # friends
    suppliers = []
    prev = 0
    for rec in statements:
        if not month:
            month = rec['date'].month
        elif rec['date'].month!=month: # start a new month
            # calculate non-paying members
            non_paying_members = get_non_paying_members(contributors, share)
            # calculate non-paying friends
            non_paying_friends = get_non_paying_friends(friends)

            print >>sys.stderr, "%15s\t%5.2f\t%5.2f\t%3d\t%3d\t%3d\t%s\t%s" % (rec['date'].strftime("%B %Y"),
                                                                               balance - prev,
                                                                               balance,
                                                                               len(members),
                                                                               len(suppliers),
                                                                               len(supporters),
                                                                               non_paying_members,
                                                                               list(non_paying_friends))
            month = rec['date'].month
            members = []
            supporters = []
            suppliers = []
            prev = balance
        balance += rec['value']
        if rec['value']<0:
            suppliers.append(rec['name'])
            continue

        contributor = contributors.get(rec['account'])
        if contributor:
            members.append(contributor['name'])
            if not contributor['active']: contributor['active']=True
            contributor['balance']+=rec['value']
        else:
            friend = friends.get(rec['account'])
            if friend:
                supporters.append(friend)
                friend['balance']+=rec['value']
            else:
                print >>sys.stderr, "[!] unknown contributor:", rec['name'], rec['account']

    month += 1
    members = set()
    supporters = []
    suppliers = []
    prev = balance
    for rec in latest:
        contributor = contributors.get(contrib_shortmap.get(rec['account']))
        if contributor:
            members.add(contributor['name'])
            if not contributor['active']: contributor['active']=True
            contributor['balance']+=rec['value']
        else:
            friend = friends.get(friends_shortmap.get(rec['account']))
            if friend:
                supporters.append(friend)
                friend['balance']+=rec['value']
            else:
                print >>sys.stderr, "[!] unknown contributor:", rec['text'], rec['account']

    # calculate non-paying members
    non_paying_members = get_non_paying_members(contributors, share)
    # calculate non-paying friends
    non_paying_friends = get_non_paying_friends(friends)
    print >>sys.stderr, "%15s\t%5.2f\t%5.2f\t%3d\t%3d\t%3d\t%s\t%s" % (rec['date'].strftime("%B %Y"),
                                                                       balance - prev,
                                                                       balance,
                                                                       len(members),
                                                                       len(suppliers),
                                                                       len(supporters),
                                                                       non_paying_members,
                                                                       list(non_paying_friends))
    # list members who have not yet transfered in the running month
    # todo send reminder to them?
    print >>sys.stderr, "[x] members who have not yet contributed this month\n\t", ', '.join(
        [c['name'] for c in contributors.values() if c['name'] not in members and c['active']])

totalcosts = sum(costs.values())
print >>sys.stderr, "[-] total costs:\t\t %d" % totalcosts
print >>sys.stderr, "[i] loading contributors"
contributors, contrib_shortmap = load_contributors(contributors_fname)
share = contributor_stats(contributors, totalcosts)
friends, friends_shortmap = load_friends(friends_fname)
statements = load_bankstatement(sys.argv[1])
latest = load_latest(sys.argv[2])
bankstatement_stats(statements, balance, contributors, friends, share, latest)
