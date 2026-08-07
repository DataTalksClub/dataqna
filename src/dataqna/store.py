"""DynamoDB access.

One table, one partition per room. Every question and vote for a room lives
under that room's partition key, so a room loads with a single Query and
ranking happens in memory — rooms hold hundreds of questions, not millions.

A participant's votes are keyed ``V#<participant>#<question>`` rather than
``V#<question>#<participant>`` so that "which of these has this person already
voted for" is one range query instead of a scan.
"""

import time

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from . import config

_table = None


def table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(config.TABLE_NAME)
    return _table


def now():
    return int(time.time())


def sort_key(timestamp):
    """GSI range keys are strings, so timestamps are zero-padded to sort."""
    return f"{int(timestamp):012d}"


def _room_pk(room_id):
    return f"ROOM#{room_id}"


def _conditional(func, *args, **kwargs):
    """Run a write, returning False instead of raising when its condition fails."""
    try:
        func(*args, **kwargs)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


# --- pointers ---------------------------------------------------------------


def claim_pointer(kind, value, room_id):
    return _conditional(
        table().put_item,
        Item={"PK": f"{kind}#{value}", "SK": "META", "room_id": room_id, "kind": kind},
        ConditionExpression="attribute_not_exists(PK)",
    )


def release_pointer(kind, value):
    table().delete_item(Key={"PK": f"{kind}#{value}", "SK": "META"})


def resolve_pointer(kind, value):
    item = table().get_item(Key={"PK": f"{kind}#{value}", "SK": "META"}).get("Item")
    return item.get("room_id") if item else None


# --- rooms ------------------------------------------------------------------


def put_room(room):
    item = dict(room)
    item["PK"] = _room_pk(room["room_id"])
    item["SK"] = "META"
    item["entity"] = "room"
    item["GSI1PK"] = f"STATE#{room['state']}"
    item["GSI1SK"] = sort_key(room.get("state_changed_at") or room["created_at"])
    if room.get("ttl"):
        item["ttl"] = room["ttl"]
    table().put_item(Item=item)
    return room


def get_room(room_id):
    item = table().get_item(Key={"PK": _room_pk(room_id), "SK": "META"}).get("Item")
    return item if item and item.get("entity") == "room" else None


def resolve_room(identifier):
    """Accept a room id or a slug."""
    if not identifier:
        return None
    room = get_room(identifier)
    if room:
        return room
    room_id = resolve_pointer("SLUG", identifier.lower())
    return get_room(room_id) if room_id else None


def update_room(room_id, fields):
    if not fields:
        return get_room(room_id)
    names, values, sets = {}, {}, []
    for index, (key, value) in enumerate(fields.items()):
        names[f"#f{index}"] = key
        values[f":v{index}"] = value
        sets.append(f"#f{index} = :v{index}")
    result = table().update_item(
        Key={"PK": _room_pk(room_id), "SK": "META"},
        UpdateExpression="SET " + ", ".join(sets),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ConditionExpression=Attr("PK").exists(),
        ReturnValues="ALL_NEW",
    )
    return result.get("Attributes")


def delete_room(room):
    """Remove a room and everything under its partition."""
    room_id = room["room_id"]
    items = table().query(KeyConditionExpression=Key("PK").eq(_room_pk(room_id)))["Items"]
    with table().batch_writer() as batch:
        for item in items:
            batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
    if room.get("slug"):
        release_pointer("SLUG", room["slug"])


def rooms_for_user(email):
    grants = table().query(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq(f"USER#{email.lower()}"),
    )["Items"]
    rooms = []
    for grant in grants:
        room = get_room(grant["room_id"])
        if room:
            rooms.append(room)
    return rooms


def rooms_by_state(state, limit=25, since=None):
    """Rooms in a state, newest first. `since` is an epoch cutoff on the
    moment the room entered that state — which is what "closed this week"
    means."""
    condition = Key("GSI1PK").eq(f"STATE#{state}")
    if since is not None:
        condition = condition & Key("GSI1SK").gte(sort_key(since))
    return table().query(
        IndexName="GSI1",
        KeyConditionExpression=condition,
        ScanIndexForward=False,
        Limit=limit,
    )["Items"]


def bump_counter(room_id, field, delta):
    table().update_item(
        Key={"PK": _room_pk(room_id), "SK": "META"},
        UpdateExpression=f"ADD #f :d",
        ExpressionAttributeNames={"#f": field},
        ExpressionAttributeValues={":d": delta},
    )


# --- admin grants -----------------------------------------------------------


def add_admin(room_id, email, role="owner"):
    """Records who owns a room. Also the index that powers "your sessions"."""
    email = email.lower()
    table().put_item(
        Item={
            "PK": _room_pk(room_id),
            "SK": f"ADMIN#{email}",
            "entity": "admin",
            "room_id": room_id,
            "email": email,
            "role": role,
            "GSI1PK": f"USER#{email}",
            "GSI1SK": _room_pk(room_id),
            "created_at": now(),
        }
    )


def is_admin(room_id, email):
    if not email:
        return False
    email = email.lower()
    if email in config.ROOT_ADMINS:
        return True
    item = table().get_item(Key={"PK": _room_pk(room_id), "SK": f"ADMIN#{email}"}).get("Item")
    return item is not None


# --- questions --------------------------------------------------------------


def put_question(question):
    item = dict(question)
    item["PK"] = _room_pk(question["room_id"])
    item["SK"] = f"Q#{question['question_id']}"
    item["entity"] = "question"
    if question.get("ttl"):
        item["ttl"] = question["ttl"]
    table().put_item(Item=item)
    return question


def get_question(room_id, question_id):
    item = table().get_item(Key={"PK": _room_pk(room_id), "SK": f"Q#{question_id}"}).get("Item")
    return item if item and item.get("entity") == "question" else None


def list_questions(room_id):
    items, kwargs = [], {}
    while True:
        page = table().query(
            KeyConditionExpression=Key("PK").eq(_room_pk(room_id)) & Key("SK").begins_with("Q#"),
            **kwargs,
        )
        items.extend(page["Items"])
        if not page.get("LastEvaluatedKey"):
            return items
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def update_question(room_id, question_id, fields):
    names, values, sets = {}, {}, []
    for index, (key, value) in enumerate(fields.items()):
        names[f"#f{index}"] = key
        values[f":v{index}"] = value
        sets.append(f"#f{index} = :v{index}")
    result = table().update_item(
        Key={"PK": _room_pk(room_id), "SK": f"Q#{question_id}"},
        UpdateExpression="SET " + ", ".join(sets),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ConditionExpression=Attr("PK").exists(),
        ReturnValues="ALL_NEW",
    )
    return result.get("Attributes")


def delete_question(room_id, question_id):
    table().delete_item(Key={"PK": _room_pk(room_id), "SK": f"Q#{question_id}"})


# --- votes ------------------------------------------------------------------


def add_vote(room_id, question_id, participant, ttl=None):
    """Record a vote, returning False when this participant already voted."""
    item = {
        "PK": _room_pk(room_id),
        "SK": f"V#{participant}#{question_id}",
        "entity": "vote",
        "question_id": question_id,
        "created_at": now(),
    }
    if ttl:
        item["ttl"] = ttl
    if not _conditional(table().put_item, Item=item, ConditionExpression="attribute_not_exists(SK)"):
        return False
    table().update_item(
        Key={"PK": _room_pk(room_id), "SK": f"Q#{question_id}"},
        UpdateExpression="ADD score :one",
        ExpressionAttributeValues={":one": 1},
    )
    return True


def remove_vote(room_id, question_id, participant):
    removed = _conditional(
        table().delete_item,
        Key={"PK": _room_pk(room_id), "SK": f"V#{participant}#{question_id}"},
        ConditionExpression="attribute_exists(SK)",
    )
    if not removed:
        return False
    table().update_item(
        Key={"PK": _room_pk(room_id), "SK": f"Q#{question_id}"},
        UpdateExpression="ADD score :minus",
        ExpressionAttributeValues={":minus": -1},
    )
    return True


def votes_for_participant(room_id, participant):
    if not participant:
        return set()
    items = table().query(
        KeyConditionExpression=Key("PK").eq(_room_pk(room_id))
        & Key("SK").begins_with(f"V#{participant}#"),
        ProjectionExpression="question_id",
    )["Items"]
    return {item["question_id"] for item in items}


# --- co-host invites --------------------------------------------------------

# An invite is two halves. The `name` sits in the URL and is not a secret — it
# only says which invite you mean. The `passcode` is the secret, and is what
# actually grants access. Splitting them means a link forwarded to the wrong
# chat, or pasted into a public channel, is not enough on its own.
#
# Both are stored in the clear under the room partition, because a host has to
# read them back and say them out loud, and both are only ever returned through
# admin-authorized endpoints. The lookup pointer is keyed on the name, which is
# not secret, so nothing sensitive sits outside the room's partition.


def normalize_cohost_code(value):
    return "".join(str(value or "").split()).replace("-", "").upper()


def normalize_cohost_name(value):
    return "".join(str(value or "").strip().lower().split())


def put_cohost_invite(invite):
    item = dict(invite)
    item["PK"] = _room_pk(invite["room_id"])
    item["SK"] = f"COHOST#{invite['invite_id']}"
    item["entity"] = "cohost_invite"
    table().put_item(Item=item)
    return invite


def _cohost_name_pk(room_id, name):
    """Scoped to the room, so a name only has to be free within its session."""
    return f"COHOSTNAME#{room_id}#{normalize_cohost_name(name)}"


def claim_cohost_name(name, room_id, invite_id):
    item = {
        "PK": _cohost_name_pk(room_id, name),
        "SK": "META",
        "entity": "cohost_pointer",
        "room_id": room_id,
        "invite_id": invite_id,
    }
    return _conditional(
        table().put_item, Item=item, ConditionExpression="attribute_not_exists(PK)"
    )


def list_cohost_invites(room_id):
    items = table().query(
        KeyConditionExpression=Key("PK").eq(_room_pk(room_id)) & Key("SK").begins_with("COHOST#")
    )["Items"]
    return sorted(items, key=lambda item: item.get("created_at", 0), reverse=True)


def get_cohost_invite(room_id, invite_id):
    item = table().get_item(
        Key={"PK": _room_pk(room_id), "SK": f"COHOST#{invite_id}"}
    ).get("Item")
    return item if item and item.get("entity") == "cohost_invite" else None


def revoke_cohost_invite(room_id, invite_id):
    invite = get_cohost_invite(room_id, invite_id)
    if not invite:
        return False
    table().delete_item(Key={"PK": _room_pk(room_id), "SK": f"COHOST#{invite_id}"})
    # The name goes back into circulation with the invite that held it.
    table().delete_item(Key={"PK": _cohost_name_pk(room_id, invite["name"]), "SK": "META"})
    return True


def resolve_cohost_name(room_id, name):
    """Find a room's invite by its link name. Says nothing about the passcode."""
    normalized = normalize_cohost_name(name)
    if not normalized:
        return None
    pointer = table().get_item(
        Key={"PK": _cohost_name_pk(room_id, normalized), "SK": "META"}
    ).get("Item")
    if not pointer or pointer.get("entity") != "cohost_pointer":
        return None
    return get_cohost_invite(pointer["room_id"], pointer["invite_id"])


# --- api keys ---------------------------------------------------------------


def put_api_key(record):
    item = dict(record)
    item["PK"] = f"KEY#{record['key_hash']}"
    item["SK"] = "META"
    item["entity"] = "api_key"
    item["GSI1PK"] = f"USER#{record['email']}"
    item["GSI1SK"] = f"KEY#{record['key_id']}"
    table().put_item(Item=item)
    return record


def get_api_key(key_hash):
    item = table().get_item(Key={"PK": f"KEY#{key_hash}", "SK": "META"}).get("Item")
    return item if item and item.get("entity") == "api_key" else None


def list_api_keys(email):
    items = table().query(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq(f"USER#{email.lower()}")
        & Key("GSI1SK").begins_with("KEY#"),
    )["Items"]
    return sorted(items, key=lambda item: item.get("created_at", 0), reverse=True)


def delete_api_key(key_hash):
    table().delete_item(Key={"PK": f"KEY#{key_hash}", "SK": "META"})


def touch_api_key(key_hash):
    table().update_item(
        Key={"PK": f"KEY#{key_hash}", "SK": "META"},
        UpdateExpression="SET last_used_at = :t",
        ExpressionAttributeValues={":t": now()},
    )


# --- rate limiting ----------------------------------------------------------


def rate_allow(scope, window_seconds, limit):
    """Fixed-window counter. Returns False once the window's limit is spent."""
    window = now() // window_seconds
    try:
        result = table().update_item(
            Key={"PK": f"RATE#{scope}", "SK": str(window)},
            UpdateExpression="ADD hits :one SET #ttl = :ttl",
            ExpressionAttributeNames={"#ttl": "ttl"},
            ExpressionAttributeValues={
                ":one": 1,
                ":ttl": (window + 2) * window_seconds,
                ":limit": limit,
            },
            ConditionExpression="attribute_not_exists(hits) OR hits < :limit",
            ReturnValues="UPDATED_NEW",
        )
        return True, int(result["Attributes"]["hits"])
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False, limit
        raise


# --- idempotency ------------------------------------------------------------


def claim_idempotency(email, key, room_id, ttl_seconds=86400):
    scope = f"IDEM#{email.lower()}#{key}"
    if _conditional(
        table().put_item,
        Item={
            "PK": scope,
            "SK": "META",
            "entity": "idempotency",
            "room_id": room_id,
            "ttl": now() + ttl_seconds,
        },
        ConditionExpression="attribute_not_exists(PK)",
    ):
        return None
    existing = table().get_item(Key={"PK": scope, "SK": "META"}).get("Item")
    return existing.get("room_id") if existing else None
