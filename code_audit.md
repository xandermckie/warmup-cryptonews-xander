## app.py functions:

index()
1. What does this function do? This function reads the data/cache.json, renders the index.html, and adds all necessary variables like coins, news, last_updated, etc.
2. What does it take as input, and what does it return? No input, returns html page w content
3. What happens if the input is wrong or missing? no user input, but .get() handles any issues w missing keys
4. Is there a simpler way to write this? i don't think so

search()
1. What does this function do? This searches cached coins by string and returns results as json.
2. What does it take as input, and what does it return? take url, returns json obj
3. What happens if the input is wrong or missing? returns 400 error if anything is missing or oversized
4. Is there a simpler way to write this? it could be slightly simpler according to claude, but this way makes it easier for me to read

coin_detail(coin_id)
1. What does this function do? fetches and returns the details of each coin
2. What does it take as input, and what does it return? takes coin_id from the api and returns jon w the metadata
3. What happens if the input is wrong or missing? if no info returns it gives 400 error
4. Is there a simpler way to write this? no

coin_chart(coin_id)
1. What does this function do? fetches historical price data over specific time range
2. What does it take as input, and what does it return? takes coin_id and days and returns json w price history
3. What happens if the input is wrong or missing? if anything is missing like coind id, non-integer days, etc, it gives specific error msgs
4. Is there a simpler way to write this? It looks like I could improve this by combining the int() convrsion and range check into a helper function if it is used elsewhere in the future

not_found and server_error
1. What does this function do? they catch 404 and 500 errors and give error pages instead of default flask msgs
2. What does it take as input, and what does it return? takes error obj, return html template w code and message
3. What happens if the input is wrong or missing? error parameter is always valid (from flask) templates render clean
4. Is there a simpler way to write this? no, this is standard

## fetcher.py functions:

_empty_cache()
1. What does this function do? creates a blank cache w all req keys ready to go
2. What does it take as input, and what does it return? returns a dict w variables
3. What happens if the input is wrong or missing? no input
4. Is there a simpler way to write this? no

_strip_html()
1. What does this function do? removes html tags from coingecks desriptions to get plain text
2. What does it take as input, and what does it return? takes html string returns cleaned plain text w whitespace trimmed
3. What happens if the input is wrong or missing? handles none with or fallback using regex
4. Is there a simpler way to write this? no

is_valid_coin_id()
1. What does this function do? validates that a coin id matches coingeckos format before making any api calls
2. What does it take as input, and what does it return? takes coin id string and returns true if it is valid or false otherwise
3. What happens if the input is wrong or missing? empty string or non-matching format returns false, prevents invalid api calls
4. Is there a simpler way to write this? no

format_last_updated()
1. What does this function do? converts a utc iso timestamp to cst string
2. What does it take as input, and what does it return? takes og stamp and returns formatted string or "never" if missing 
3. What happens if the input is wrong or missing? handles malformed timestampes by catching valueerror and falling back to rawstring 
4. Is there a simpler way to write this? small change would be "the lstrip("0") or "12" for 12-hour format is clever but a bit cryptic. You could use cst.strftime("%#I") on Unix (or %-I) to avoid zero-padding, but it's platform-dependent."

_is_rate_limited()
1. What does this function do? checks if a request exception is a 429 error from coingecko
2. What does it take as input, and what does it return? takes a requests.requestexception; returns true if 429, false otherwise
3. What happens if the input is wrong or missing? handles exceptions without a .response by ussing getattr() w a default
4. Is there a simpler way to write this? no

load_cache()
1. What does this function do? reads the cache file from disk; returns empty skeleton if missing, corrupt, or missing keys
2. What does it take as input, and what does it return? takes no parameters; returns a dict w all expected cache keys populated
3. What happens if the input is wrong or missing? handles missing file, invalid json, and partially filled cache by filling in gaps w defaults
4. Is there a simpler way to write this? could use json.load() w object hooks but your explicit key checking approach is more readable and safer for schema changes

save_cache()
1. What does this function do? writes the cache dict to disk as formatted json
2. What does it take as input, and what does it return? takes a cache dict; returns nothing (side effect: writes files)
3. What happens if the input is wrong or missing? creates a parent dir automatically if they dont exist, no validation of dict contents needed
4. Is there a simpler way to write this? no

fetch_coins()
1. What does this function do? call coingeckos markets endpt to get the top 50 coins by market cap
2. What does it take as input, and what does it return? takes no params, returns list of coin dicts w flattened fields
3. What happens if the input is wrong or missing? raise_for_status() handles http errors; no user input to validate
4. Is there a simpler way to write this? slight, "the field extraction could use a dict comprehension or loop over a keys list to avoid repetition if you add more coins later, but for 50 coins this is fine."

_fetch_genesis_date()
1. What does this function do? calls coingeckos lightweight coin detail enpt to fetch just the genesis_date field
2. What does it take as input, and what does it return? takes a coin idl returns a date string or none
3. What happens if the input is wrong or missing? no validation here, assumes caller (enrich_coins_with_genesis) has already validated ID
4. Is there a simpler way to write this? no

enrich_coins_with_genesis()
1. What does this function do? attaches genesis dates to coins, reusing cached dates and only fetching missing ones in batches to prevent overcalling api (ratelimiting)
2. What does it take as input, and what does it return? takes a coin list and optional prev cache, returns enriched coin list w genesis_date fields populated
3. What happens if the input is wrong or missing? handles none for previous_coins, loops through coins safely
4. Is there a simpler way to write this? missing a comment to explain the strategy

get_coin_from_cache()
1. What does this function do? looks up a single coin by id from the on-disk cache (used as fallback when live api calls fail)
2. What does it take as input, and what does it return? takes a coin id; returns the coin dict or none if not found
3. What happens if the input is wrong or missing? handles missing id by returnning none
4. Is there a simpler way to write this? "Could use a next() with a generator: next((c for c in ... if c.get("id") == coin_id), None), but your loop is clearer."

compute_pick_of_day()
1. What does this function do? ranks coins using a momentum + val heuristic (favors established coins below all time high w pos 24h movement) and returns the winner w a human readable reason
2. What does it take as input, and what does it return? takes a coin list; returns a dict with the picked ocins metadata + reason string or none
3. What happens if the input is wrong or missing? handles empty list, missing fields, and edge cases, falls back to top 10 if no top 30 candidates exist
4. Is there a simpler way to write this? not really, but "Could extract the scoring to a helper function if you add more heuristics later, but for now it's self-contained and fine."

fetch_wikipedia_summary()
1. What does this function do? fetches a short wiki summary for coin name
2. What does it take as input, and what does it return? takes a title string, returns a dict with {title, extract, url} or none if not found
3. What happens if the input is wrong or missing? handles request failures by returning none
4. Is there a simpler way to write this? no

fetch_coin_detail()
1. What does this function do? fetches rich metadata for a coin for the modal, falls back to cached data if coingecko is down or ratelimited
2. What does it take as input, and what does it return? takes a coin id; returns dict w metadata + fallback flag if applicable
3. What happens if the input is wrong or missing? validates coin id format first; catches req exceptions and builds a fallback response w partial data from cache
4. Is there a simpler way to write this? not really but i could, "extract the fallback response-building into a helper, but it's only called once so inline is defensible."

fetch_coin_chart()
1. What does this function do? fetches historical price data from coingecko for a specific coin over # days
2. What does it take as input, and what does it return? takes coin id and days and returns dict w {days, prices: [{timestamp, price}, ...], source} or error
3. What happens if the input is wrong or missing? validates both coin id and days param, catches req exceptions and returns an "unavailable" flag instead of crashing
4. Is there a simpler way to write this? no

fetch_news()
1. What does this function do? fetches crypto related news headlines from newsAPI
2. What does it take as input, and what does it return? takes no params, returns list of article dicts w normalized fields
3. What happens if the input is wrong or missing? checks for missing api key early, validates api response status, handles missing fields w .get() and defaults
4. Is there a simpler way to write this? no

refresh_cache()
1. What does this function do? orchestrates a full cache refresh, fetches fresh coins and news and info and writes to disk
2. What does it take as input, and what does it return? takes no params, returns cache dict
3. What happens if the input is wrong or missing? handles partial fails by keeping old data and marking cache as stale, only flags full failure if no data was fetched and cache is empty
4. Is there a simpler way to write this? no

filter_cache()
1. What does this function do? searches cached coins and news by query string
2. What does it take as input, and what does it return? takes a query string and optional cache dict, returns filtered results dict w coins news metadata
3. What happens if the input is wrong or missing? andles empty query by returning all coins / news, loads cache from disk if not provided
4. Is there a simpler way to write this? no

## 2 Function Changes
app.py search()
Completely rewrote and remove the redundant if q is None block. Changed because originally it was pointless to have q is none because we already return "" if its empty.


fetcher.py fetch_coins()
completely rewrote to only define the field names once so it is easy to add and remove fields without repeating keys in the future