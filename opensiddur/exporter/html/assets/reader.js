/*
 * The page script of an Open Siddur electronic book.
 *
 * The page arrives showing what the printed book shows for the same settings: the rules in
 * <style id="os-cond-default">, computed when the book was built. This script takes over from
 * them. It resolves every undecided passage against the reader's own settings, kept in this
 * browser, and against the day: the device's clock, at the place the reader gives. It writes
 * the result into <style id="os-cond-live">, and redoes it whenever a setting changes, and as
 * the day goes on -- at nightfall the book moves to the next day. Without it -- no scripting, as
 * in most EPUB readers -- the page is the printed book.
 *
 * Nothing leaves the device: no network access, no tracking. The device's location is asked for
 * only when the reader asks the settings panel to use it.
 */
(function () {
  "use strict";

  var book = JSON.parse(document.getElementById("os-book").textContent);
  var storageKey = "opensiddur:" + book.id + ":settings";
  var liveStyle = document.getElementById("os-cond-live");
  var defaultStyle = document.getElementById("os-cond-default");

  // Every file:// page shares one origin, so the key carries the book's id. Storage can be
  // refused (a private window, a locked-down reader); the book still works, unremembered.
  function loadSettings() {
    try {
      var stored = JSON.parse(window.localStorage.getItem(storageKey));
      return stored && typeof stored === "object" ? stored : {};
    } catch (e) {
      return {};
    }
  }

  function saveSettings(settings) {
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(settings));
    } catch (e) {
      /* not remembered */
    }
  }

  var reader = loadSettings();

  // ── The day ────────────────────────────────────────────────────────────
  //
  // How the book knows what day it is (calendar.mode):
  //   "now"    -- from the device's clock, kept up to date while the book is open;
  //   "chosen" -- a date and time the reader chose;
  //   "none"   -- no particular day: the reader sets the kind of day by hand, if at all.
  // The place is the reader's: coordinates and a time zone, in reader["opensiddur:location"],
  // with its name and where it came from in calendar.place. A chosen date and time are the
  // reader's too, in reader["opensiddur:gregorian-date"] and reader["opensiddur:time"]. The
  // clock's time is never saved: it is read afresh.

  var FS_GREGORIAN = "opensiddur:gregorian-date";
  var FS_TIME = "opensiddur:time";
  var FS_LOCATION = "opensiddur:location";
  var calendarKey = "opensiddur:" + book.id + ":calendar";
  var hasCalendar = Boolean(book.calendarScopes);

  // The features the controls marked `when` (basic_settings.yaml) set: "no-date" for no
  // particular day, "no-place" for no place.
  function controlFeatures(when) {
    var keys = [];
    (book.basic || []).forEach(function (entry) {
      if (entry.type !== "control" || entry.when !== when) return;
      entry.options.forEach(function (option) {
        Object.keys(option.set).forEach(function (fs) {
          Object.keys(option.set[fs]).forEach(function (name) { keys.push([fs, name]); });
        });
      });
    });
    return keys;
  }

  function noDateFeatures() {
    return controlFeatures("no-date");
  }

  function loadCalendar() {
    var stored = null;
    try {
      stored = JSON.parse(window.localStorage.getItem(calendarKey));
    } catch (e) {
      stored = null;
    }
    if (stored && typeof stored === "object" &&
        ["now", "chosen", "none"].indexOf(stored.mode) >= 0) {
      var where = stored.place || null;
      // Where the device was, until it says where it is now (refreshLocation).
      if (where && where.source === "geolocation") where.name = "Your last known location";
      return { mode: stored.mode, place: where };
    }
    // A reader who set the kind of day by hand before the book could tell the day keeps it;
    // otherwise the book starts as its settings file says (book.start).
    var manual = noDateFeatures().some(function (k) { return has(k[0], k[1]); });
    return { mode: manual ? "none" : startingMode(), place: null };
  }

  function startingMode() {
    return book.start && book.start.day === "none" ? "none" : "now";
  }

  function saveCalendar() {
    try {
      window.localStorage.setItem(calendarKey, JSON.stringify(calendar));
    } catch (e) {
      /* not remembered */
    }
  }

  // The time now: window.opensiddurClock, if a page embedding the book (or a test) gives one.
  function now() {
    return typeof window.opensiddurClock === "function" ? window.opensiddurClock() : new Date();
  }

  function place() {
    var location = reader[FS_LOCATION];
    return location && typeof location.latitude === "number" &&
      typeof location.longitude === "number" && location.timezone ? location : null;
  }

  // The wall clock in a zone (the device's own, for none): {year, month, day, hour, minute}.
  function wallClock(date, zone) {
    var options = { hourCycle: "h23", year: "numeric", month: "numeric", day: "numeric",
                    hour: "numeric", minute: "numeric" };
    var parts = {};
    var format;
    try {
      format = new Intl.DateTimeFormat("en-US", zone ? Object.assign({ timeZone: zone }, options)
                                                      : options);
    } catch (e) {
      format = new Intl.DateTimeFormat("en-US", options);
    }
    format.formatToParts(date).forEach(function (part) { parts[part.type] = Number(part.value); });
    return { year: parts.year, month: parts.month, day: parts.day, hour: parts.hour % 24,
             minute: parts.minute };
  }

  // What the device knows by itself: the date and the time, at the place, in "now" mode.
  function deviceLayer() {
    if (!hasCalendar || calendar.mode !== "now") return {};
    var where = place();
    var clock = wallClock(now(), where ? where.timezone : null);
    var layer = {};
    layer[FS_GREGORIAN] = { year: clock.year, month: clock.month, day: clock.day };
    layer[FS_TIME] = { hour: clock.hour, minute: clock.minute };
    return layer;
  }

  // The reader's settings as they apply in the mode: no chosen day but in "chosen", and no
  // place for no particular day.
  function readerLayer() {
    var omit = calendar.mode === "chosen" ? [] :
      calendar.mode === "now" ? [FS_GREGORIAN, FS_TIME] : [FS_GREGORIAN, FS_TIME, FS_LOCATION];
    if (!hasCalendar || !omit.some(function (fs) { return reader[fs]; })) return reader;
    var layer = {};
    Object.keys(reader).forEach(function (fs) {
      if (omit.indexOf(fs) < 0) layer[fs] = reader[fs];
    });
    return layer;
  }

  // Whether the book works out the day: it has one, and a place to work it out at.
  function following() {
    return hasCalendar && calendar.mode !== "none" && place() !== null;
  }

  var calendar = loadCalendar();

  // ── What is shown ──────────────────────────────────────────────────────
  //
  // A display preference, not a setting the text turns on: which columns of the parallel text
  // are shown -- both, or one (book.columns names them). Kept beside the settings.

  var displayKey = "opensiddur:" + book.id + ":display";

  // The book's own starting columns (book.start), until the reader chooses.
  function startingDisplay() {
    var columns = book.start && book.start.columns;
    return columns === "primary" || columns === "parallel" ? { columns: columns } : {};
  }

  function loadDisplay() {
    try {
      var stored = JSON.parse(window.localStorage.getItem(displayKey));
      return stored && typeof stored === "object" ? stored : startingDisplay();
    } catch (e) {
      return startingDisplay();
    }
  }

  function saveDisplay() {
    try {
      window.localStorage.setItem(displayKey, JSON.stringify(display));
    } catch (e) {
      /* not remembered */
    }
  }

  var display = loadDisplay();

  // The column shown alone, "primary" or "parallel", or null for both.
  function shownColumns() {
    return book.columns && (display.columns === "primary" || display.columns === "parallel")
      ? display.columns : null;
  }
  var lastDevice = null;
  var statusListeners = [];

  // The structures that say what day it is. A reader who sets one of them by hand to other
  // than what the date gives has said the day is another one: the date is set aside, and
  // with it everything it implies -- the clock, a chosen day, the place.
  var DAY_FS_TYPES = ["opensiddur:holiday-aggregate", "opensiddur:holiday",
                      "opensiddur:day-of-week", "opensiddur:hebrew-date"];

  function sameDayValue(a, b) {
    var plainNumber = function (v) {
      if (v !== null && typeof v === "object" && "num" in v) return v.num;
      return typeof v === "boolean" ? Number(v) : v;
    };
    return plainNumber(a) === plainNumber(b);
  }

  function omitting(layer, fsTypes) {
    var out = {};
    Object.keys(layer).forEach(function (fs) { if (fsTypes.indexOf(fs) < 0) out[fs] = layer[fs]; });
    return out;
  }

  function contradictsTheDate(layer, device) {
    var own = DAY_FS_TYPES.filter(function (fs) { return layer[fs]; });
    if (!own.length) return false;
    var dated = new OSCond.Resolver(omitting(layer, DAY_FS_TYPES), book.defaults, device)
      .settings({});
    return own.some(function (fs) {
      return Object.keys(layer[fs]).some(function (name) {
        var mine = layer[fs][name], theirs = plain((dated[fs] || {})[name]);
        return mine !== null && theirs !== null && theirs !== undefined && !sameDayValue(mine, theirs);
      });
    });
  }

  var dateSetAside = false;

  function resolveAll() {
    var device = deviceLayer();
    lastDevice = JSON.stringify(device);
    var layer = readerLayer();
    dateSetAside = following() && contradictsTheDate(layer, device);
    if (dateSetAside) {
      device = {};
      layer = omitting(layer, [FS_GREGORIAN, FS_TIME, FS_LOCATION]);
    }
    var result = OSCond.scopeCss(book, layer, book.defaults, device);
    result.settings = result.resolver.settings({});
    return result;
  }

  // A live region is announced when it changes: write it only when what it says does.
  function say(element, text) {
    if (element.textContent !== text) element.textContent = text;
  }

  // The first passage on screen, below the toolbar, and where it is.
  // In the book's text, not in the settings dialog over it. Several passages down the
  // screen, the first first: a change can hide the one at the top.
  function anchor() {
    if (!document.elementsFromPoint) return null;
    var x = window.innerWidth / 2;
    var top = (toolbar ? toolbar.offsetHeight : 0) + 8;
    var candidates = [];
    for (var y = top; y < window.innerHeight; y += 60) {
      var element = document.elementsFromPoint(x, y).find(function (hit) {
        return hit.closest && hit.closest(".os-book");
      });
      // The row it is in: the innermost, since a row can hold others, and a row's top does not
      // move when what is inside it changes. The rows around are held laid out while the change
      // settles (holdNearRows), so it is measured where it is.
      element = (element && element.closest(".par")) || element;
      if (element && !candidates.some(function (c) { return c.element === element; })) {
        candidates.push({ element: element, top: element.getBoundingClientRect().top });
      }
    }
    return candidates.length ? candidates : null;
  }

  // Keep the passage the reader is at where it is when what shows above it changes. Rows off
  // screen take their real heights only once laid out (content-visibility: auto), which moves
  // the passage again after a first correction: correct it each time it settles somewhere
  // else, until it settles in place, or until the reader scrolls.
  var keeping = 0;
  // The rows around the reader's place -- three screens up and down, and the rows inside them
  // -- laid out until the change has settled: the place's position depends on their heights,
  // and a row reached for the first time takes its own only then.
  var allRows = null;
  function holdNearRows() {
    allRows = allRows || Array.prototype.slice.call(document.querySelectorAll(".par"));
    var low = -3 * window.innerHeight, high = 4 * window.innerHeight;
    var near = allRows.filter(function (row) {
      var box = row.getBoundingClientRect();
      return box.height && box.bottom > low && box.top < high;
    });
    near.forEach(function (row) { row.classList.add("os-near"); });
    return near;
  }

  function releaseRows(rows) {
    (rows || []).forEach(function (row) { row.classList.remove("os-near"); });
  }

  function keepInPlace(candidates, near) {
    var kept = (candidates || []).find(function (c) { return c.element.getClientRects().length; });
    if (!kept) return releaseRows(near);
    var element = kept.element;
    var run = ++keeping, frames = 0, still = 0, last = null;
    (function correct() {
      if (run !== keeping) return releaseRows(near);
      // Wait for the layout to stop moving before correcting: correcting while rows are
      // still taking their heights chases them, back and forth.
      var top = element.getBoundingClientRect().top;
      still = last !== null && Math.abs(top - last) <= 1 ? still + 1 : 0;
      last = top;
      if (still >= 2) {
        var moved = top - kept.top;
        if (Math.abs(moved) <= 1) return releaseRows(near);
        window.scrollBy(0, moved);
        last = null;
        still = 0;
      }
      if (++frames < 120) requestAnimationFrame(correct);
      else releaseRows(near);
    })();
  }

  var applied = false;
  var lastSettings = {};
  // While the settings dialog is open over the book, the passage that was on screen when it
  // opened: the book under a modal dialog cannot be found by where it is on screen.
  var heldAnchor = null;

  function apply() {
    var result = resolveAll();
    var page = document.documentElement;
    var columns = shownColumns();
    var columnsChange = (page.getAttribute("data-columns") || null) !== columns;
    if (liveStyle.textContent !== result.css || columnsChange) {
      var before = !applied ? null : heldAnchor || anchor();
      var near = applied ? holdNearRows() : [];
      if (liveStyle.textContent !== result.css) liveStyle.textContent = result.css;
      if (columns) page.setAttribute("data-columns", columns);
      else page.removeAttribute("data-columns");
      keepInPlace(before, near);
    }
    defaultStyle.disabled = true;
    applied = true;
    lastSettings = result.settings;
    statusListeners.forEach(function (listener) { listener(result.settings); });
    return result;
  }

  // In "now" mode, follow the clock: the text changes at the moments the day does -- dawn,
  // nightfall -- whether the book is in view or comes back into it.
  function tick() {
    if (calendar.mode !== "now" || !hasCalendar) return;
    if (JSON.stringify(deviceLayer()) !== lastDevice) apply();
  }

  // ── Words for the settings panel ───────────────────────────────────────

  function words(name) {
    var text = String(name).replace(/^[a-z]+:/, "").replace(/[-_]/g, " ");
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  function describe(value) {
    if (value === true) return "Yes";
    if (value === false) return "No";
    if (value !== null && typeof value === "object" && "num" in value) {
      return "max" in value ? value.num + "–" + value.max : String(value.num);
    }
    return words(value);
  }

  // A value the reader can set: a condition's range becomes its first number.
  function settable(value) {
    if (value !== null && typeof value === "object" && "num" in value) return value.num;
    return value;
  }

  function el(tag, attributes, children) {
    var element = document.createElement(tag);
    Object.keys(attributes || {}).forEach(function (key) {
      if (key === "text") element.textContent = attributes[key];
      else element.setAttribute(key, attributes[key]);
    });
    (children || []).forEach(function (child) { element.appendChild(child); });
    return element;
  }

  function sameValue(a, b) {
    return JSON.stringify(a) === JSON.stringify(b);
  }

  // ── The reader's settings ──────────────────────────────────────────────

  var features = {};
  book.features.forEach(function (feature) {
    features[feature.fs + "\u0000" + feature.name] = feature;
  });

  function has(fs, name) {
    return !!reader[fs] && Object.prototype.hasOwnProperty.call(reader[fs], name);
  }

  // undefined clears the reader's setting, so the book's default applies again; null is the
  // reader's own "show every option".
  function setValue(fs, name, value) {
    if (value === undefined) {
      if (reader[fs]) {
        delete reader[fs][name];
        if (!Object.keys(reader[fs]).length) delete reader[fs];
      }
    } else {
      (reader[fs] = reader[fs] || {})[name] = value;
    }
  }

  var refreshers = [];

  // A change previews at once; it is kept (saved) only when the reader says Done.
  function changed() {
    apply();
    refreshers.forEach(function (refresh) { refresh(); });
  }

  function featureLabel(feature) {
    return feature.label || words(feature.name);
  }

  function valueLabel(feature, value) {
    var labels = feature.valueLabels || {};
    var key = String(settable(value));
    return Object.prototype.hasOwnProperty.call(labels, key) ? labels[key] : describe(value);
  }

  // ── Controls ───────────────────────────────────────────────────────────

  var UNSET = "Not set — show every option";
  var FOLLOWS = "Not set — follows the day";

  // Whether a control marked `when` (basic_settings.yaml) is for the way the day is known now.
  function shownInMode(when) {
    if (when === "no-date") return !hasCalendar || calendar.mode === "none";
    if (when === "no-place") return !following();
    return true;
  }

  var controlCount = 0;

  function row(label, control, note) {
    var id = "os-setting-" + (controlCount++);
    control.id = id;
    var children = [el("label", { for: id, text: label }), control];
    if (note) {
      control.setAttribute("aria-describedby", id + "-note");
      children.push(el("span", { id: id + "-note", class: "os-setting-count", text: note }));
    }
    return el("div", { class: "os-setting" }, children);
  }

  function passages(count) {
    return count === 1 ? "1 passage" : count + " passages";
  }

  // A composite control (basic_settings.yaml): each option sets several features at once.
  function compositeControl(entry) {
    var keys = [];
    entry.options.forEach(function (option) {
      Object.keys(option.set).forEach(function (fs) {
        Object.keys(option.set[fs]).forEach(function (name) {
          if (!keys.some(function (k) { return k[0] === fs && k[1] === name; })) keys.push([fs, name]);
        });
      });
    });
    var defaults = keys.filter(function (k) {
      var set = book.defaults[k[0]];
      return set && set[k[1]] !== undefined && set[k[1]] !== null;
    });
    var select = el("select");
    var unset = null;
    if (defaults.length) {
      // The book's own choice, by the option it amounts to if there is one.
      var bookChoice = entry.options.find(function (option) {
        return Object.keys(option.set).every(function (fs) {
          return Object.keys(option.set[fs]).every(function (name) {
            var set = book.defaults[fs];
            return set && sameValue(set[name], option.set[fs][name]);
          });
        });
      });
      select.appendChild(el("option", { value: "", text: "The book's default" +
        (bookChoice ? " — " + bookChoice.label : "") }));
      select.appendChild(el("option", { value: "null", text: "Show every option" }));
    } else {
      unset = el("option", { value: "", text: UNSET });
      select.appendChild(unset);
    }
    var onCalendar = keys.every(function (k) {
      var feature = features[k[0] + "\u0000" + k[1]];
      return !feature || feature.calendar;
    });
    entry.options.forEach(function (option, index) {
      select.appendChild(el("option", { value: String(index), text: option.label }));
    });
    var custom = el("option", { value: "custom", text: "Custom (set in Advanced)", disabled: "" });
    select.appendChild(custom);

    function matches(option) {
      return Object.keys(option.set).every(function (fs) {
        return Object.keys(option.set[fs]).every(function (name) {
          return has(fs, name) && sameValue(reader[fs][name], option.set[fs][name]);
        });
      });
    }

    function everyOption() {
      return keys.every(function (k) { return has(k[0], k[1]) && reader[k[0]][k[1]] === null; });
    }

    function refresh() {
      var found = entry.options.findIndex(matches);
      var any = keys.some(function (k) { return has(k[0], k[1]); });
      var every = defaults.length && everyOption();
      custom.hidden = found >= 0 || every || !any;
      select.value = found >= 0 ? String(found) : every ? "null" : (any ? "custom" : "");
      if (unset) unset.textContent = onCalendar && following() ? FOLLOWS : UNSET;
      control.hidden = !shownInMode(entry.when);
    }

    select.addEventListener("change", function () {
      keys.forEach(function (k) { setValue(k[0], k[1], undefined); });
      if (select.value === "null") {
        // The reader's own "show every option", over the book's default.
        keys.forEach(function (k) { setValue(k[0], k[1], null); });
      } else if (select.value !== "") {
        var option = entry.options[Number(select.value)];
        Object.keys(option.set).forEach(function (fs) {
          Object.keys(option.set[fs]).forEach(function (name) {
            setValue(fs, name, option.set[fs][name]);
          });
        });
      }
      changed();
    });
    var control = row(entry.label, select, entry.note);
    refreshers.push(refresh);
    refresh();
    return control;
  }

  // One feature: a select of its values, or for a number without names, a number field.
  function featureControl(feature, label) {
    var fallback = book.defaults[feature.fs] && book.defaults[feature.fs][feature.name];
    var hasDefault = fallback !== undefined && fallback !== null;
    var values = feature.values.map(settable).filter(function (value, i, all) {
      return all.findIndex(function (other) { return sameValue(other, value); }) === i;
    });
    var named = feature.valueLabels && Object.keys(feature.valueLabels).length;
    if (feature.kind === "binary") values = [true, false];
    if (named) {
      values = Object.keys(feature.valueLabels).map(function (key) {
        return feature.kind === "numeric" ? Number(key) : key;
      });
    }
    var note = passages(feature.scopes);

    if (feature.kind === "numeric" && !named) {
      var input = el("input", { type: "number", inputmode: "numeric", step: "1", min: "0",
                                placeholder: hasDefault ? "Default: " + describe(fallback) : "Not set" });
      input.addEventListener("change", function () {
        // A number field reports what it cannot read as empty: that is not "unset".
        if (input.validity.badInput) {
          input.setCustomValidity("Enter a whole number, or clear the field.");
          input.reportValidity();
          return;
        }
        var text = input.value.trim();
        var number = Number(text);
        if (text !== "" && !(Number.isInteger(number) && number >= 0)) {
          input.setCustomValidity("Enter a whole number, or clear the field.");
          input.reportValidity();
          return;
        }
        input.setCustomValidity("");
        setValue(feature.fs, feature.name, text === "" ? undefined : number);
        changed();
      });
      refreshers.push(function () {
        var value = has(feature.fs, feature.name) ? reader[feature.fs][feature.name] : null;
        input.value = typeof value === "number" ? String(value) : "";
      });
      refreshers[refreshers.length - 1]();
      return row(label, input, note);
    }

    var select = el("select");
    var unset = null;
    if (hasDefault) {
      select.appendChild(el("option", { value: "", text: "The book's default — " + valueLabel(feature, fallback) }));
      select.appendChild(el("option", { value: "null", text: "Show every option" }));
    } else {
      unset = el("option", { value: "", text: UNSET });
      select.appendChild(unset);
    }
    values.forEach(function (value) {
      select.appendChild(el("option", { value: JSON.stringify(value), text: valueLabel(feature, value) }));
    });
    select.addEventListener("change", function () {
      setValue(feature.fs, feature.name, select.value === "" ? undefined : JSON.parse(select.value));
      changed();
    });
    refreshers.push(function () {
      select.value = has(feature.fs, feature.name)
        ? JSON.stringify(reader[feature.fs][feature.name]) : "";
      if (select.selectedIndex < 0) select.value = "";
      if (unset) unset.textContent = feature.calendar && following() ? FOLLOWS : UNSET;
    });
    refreshers[refreshers.length - 1]();
    return row(label, select, note);
  }

  // ── The day and the place ──────────────────────────────────────────────

  function pad(number) {
    return (number < 10 ? "0" : "") + number;
  }

  function setDay(clock) {
    reader[FS_GREGORIAN] = { year: clock.year, month: clock.month, day: clock.day };
    reader[FS_TIME] = { hour: clock.hour, minute: clock.minute };
  }

  function setPlace(location, name, source) {
    reader[FS_LOCATION] = { latitude: location.latitude, longitude: location.longitude,
                            timezone: location.timezone };
    calendar.place = { name: name, source: source };
    // What was set by hand for want of a place -- "Where", or Israel in Advanced -- would
    // override what the place says. The reader can set it again over the place.
    controlFeatures("no-place").concat([["opensiddur:israel", "is-israel"]])
      .forEach(function (k) { setValue(k[0], k[1], undefined); });
  }

  function clearPlace() {
    delete reader[FS_LOCATION];
    calendar.place = null;
  }

  function deviceZone() {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
    } catch (e) {
      return null;
    }
  }

  function zoneNames() {
    try {
      return typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : [];
    } catch (e) {
      return [];
    }
  }

  // The device's position, as a place in its own time zone. Asked for only from the panel,
  // and on opening only if the reader has already allowed it.
  //
  // The place's zone is the device's own. The device decides Israel by the zone, where the
  // compiler looks a zone up from the coordinates: the two agree unless the device's clock is
  // set for somewhere else.
  function locate(done, failed) {
    var zone = deviceZone();
    if (!navigator.geolocation || !zone) {
      failed("This device cannot give its location here. Choose a city instead.");
      return;
    }
    navigator.geolocation.getCurrentPosition(function (position) {
      done({ latitude: Math.round(position.coords.latitude * 1000) / 1000,
             longitude: Math.round(position.coords.longitude * 1000) / 1000, timezone: zone });
    }, function (error) {
      failed(error && error.code === 1
        ? "The book was not allowed to know your location. Choose a city instead."
        : "Your location could not be found. Choose a city instead.");
    }, { maximumAge: 600000, timeout: 20000 });
  }

  function validZone(zone) {
    if (!zone) return false;
    try {
      new Intl.DateTimeFormat("en-US", { timeZone: zone });
      return true;
    } catch (e) {
      return false;
    }
  }

  // Which columns of the parallel text are shown.
  function columnsControl() {
    var select = el("select");
    select.appendChild(el("option", { value: "", text: "Both" }));
    ["primary", "parallel"].forEach(function (role) {
      select.appendChild(el("option", { value: role, text: book.columns[role].label + " only" }));
    });
    select.addEventListener("change", function () {
      if (select.value) display.columns = select.value;
      else delete display.columns;
      changed();
    });
    refreshers.push(function () { select.value = shownColumns() || ""; });
    return el("div", { class: "os-basic" }, [row("Columns", select)]);
  }

  var resetDayControls = function () {};

  function dayControls() {
    var section = el("fieldset", { class: "os-day" }, [el("legend", { text: "Day and place" })]);

    var when = el("select");
    [["now", "Now — follows this device's clock"], ["chosen", "A day and time I choose"],
     ["none", "No particular day — set the kind of day below"]].forEach(function (option) {
      when.appendChild(el("option", { value: option[0], text: option[1] }));
    });
    when.addEventListener("change", function () {
      calendar.mode = when.value;
      if (calendar.mode !== "none") {
        // The kind of day set by hand would contradict the one worked out.
        noDateFeatures().forEach(function (k) { setValue(k[0], k[1], undefined); });
      }
      if (calendar.mode === "chosen" && !reader[FS_GREGORIAN]) {
        var where = place();
        setDay(wallClock(now(), where ? where.timezone : null));
      }
      changed();
    });
    section.appendChild(row("When", when));

    var date = el("input", { type: "date" });
    var time = el("input", { type: "time" });
    function chosen() {
      var d = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date.value);
      var t = /^(\d{2}):(\d{2})/.exec(time.value);
      if (!d) return;
      reader[FS_GREGORIAN] = { year: Number(d[1]), month: Number(d[2]), day: Number(d[3]) };
      if (t) reader[FS_TIME] = { hour: Number(t[1]), minute: Number(t[2]) };
      else delete reader[FS_TIME];
      changed();
    }
    date.addEventListener("change", chosen);
    time.addEventListener("change", chosen);
    var dateRow = row("Date", date, "From nightfall, the book shows the next Hebrew day.");
    var timeRow = row("Time", time, "At the place, by its clock.");
    section.appendChild(dateRow);
    section.appendChild(timeRow);

    var where = el("select");
    where.appendChild(el("option", { value: "", text: "Not set" }));
    // The device's location, once it has been used: an option only then.
    var saved = el("option", { value: "saved", text: "" });
    (book.places || []).forEach(function (p, index) {
      where.appendChild(el("option", { value: "city" + index, text: p.name }));
    });
    where.appendChild(el("option", { value: "custom", text: "Other: coordinates and time zone" }));
    var message = el("p", { class: "os-note", role: "status" });
    where.addEventListener("change", function () {
      say(message, "");
      var value = where.value;
      customOpen = value === "custom";
      if (value === "") {
        clearPlace();
      } else if (value.indexOf("city") === 0) {
        var city = book.places[Number(value.slice(4))];
        setPlace(city, city.name, "city");
      } else if (value === "custom") {
        customChanged();
        return;
      }
      changed();
    });
    section.appendChild(row("Place", where));

    // A button, not an option: the location is asked for only when the reader asks for it.
    var asking = 0;
    var useLocation = button("Use my location", "", function () {
      var request = ++asking;
      say(message, "Finding your location…");
      locate(function (location) {
        // A reply that comes after the dialog has closed, or after another request, is
        // for a choice no longer being made.
        if (request !== asking || !settingsFrame.dialog.open) return;
        customOpen = false;
        setPlace(location, "Your location", "geolocation");
        say(message, "");
        changed();
      }, function (problem) {
        if (request !== asking || !settingsFrame.dialog.open) return;
        say(message, problem);
      });
    });
    section.appendChild(el("div", { class: "os-setting" }, [el("span"), useLocation]));
    section.appendChild(message);

    var latitude = el("input", { type: "number", step: "any", min: "-90", max: "90" });
    var longitude = el("input", { type: "number", step: "any", min: "-180", max: "180" });
    var names = zoneNames();
    var zone;
    if (names.length) {
      // The list can lack the device's own zone (V8 leaves out "UTC").
      var own = deviceZone();
      if (own && names.indexOf(own) < 0) names = [own].concat(names);
      zone = el("select");
      names.forEach(function (name) { zone.appendChild(el("option", { value: name, text: name })); });
      zone.value = own || names[0];
    } else {
      zone = el("input", { type: "text", placeholder: "e.g. Europe/London",
                           value: deviceZone() || "" });
    }
    var customRows = [row("Latitude", latitude, "North is positive."),
                      row("Longitude", longitude, "East is positive."),
                      row("Time zone", zone)];
    customRows.forEach(function (r) { section.appendChild(r); });
    var customOpen = false;
    resetDayControls = function () {
      customOpen = false;
      asking++;
      say(message, "");
    };
    function customChanged() {
      customOpen = true;
      var lat = Number(latitude.value), lon = Number(longitude.value);
      if (latitude.value !== "" && longitude.value !== "" && Math.abs(lat) <= 90 &&
          Math.abs(lon) <= 180 && validZone(zone.value)) {
        setPlace({ latitude: lat, longitude: lon, timezone: zone.value }, "Other place", "custom");
      } else {
        clearPlace();
      }
      changed();
    }
    [latitude, longitude, zone].forEach(function (input) {
      input.addEventListener("change", customChanged);
    });

    var summary = el("p", { class: "os-note os-day-summary", role: "status" });
    section.appendChild(summary);
    function summarise(settings) { say(summary, describeDay(settings)); }
    statusListeners.push(summarise);
    summarise(lastSettings);

    refreshers.push(function () {
      when.value = calendar.mode;
      dateRow.hidden = timeRow.hidden = calendar.mode !== "chosen";
      var day = reader[FS_GREGORIAN], clock = reader[FS_TIME];
      date.value = day ? day.year + "-" + pad(day.month) + "-" + pad(day.day) : "";
      time.value = clock ? pad(clock.hour) + ":" + pad(clock.minute) : "";
      var at = place();
      var source = calendar.place && calendar.place.source;
      if (source === "geolocation") {
        saved.textContent = calendar.place.name;
        if (!saved.parentNode) where.insertBefore(saved, where.options[1]);
      } else if (saved.parentNode) {
        where.removeChild(saved);
      }
      if (!at) {
        where.value = customOpen ? "custom" : "";
      } else if (source === "geolocation") {
        where.value = "saved";
      } else if (source === "custom") {
        where.value = "custom";
        latitude.value = String(at.latitude);
        longitude.value = String(at.longitude);
        if (zone.tagName === "SELECT" && !Array.prototype.some.call(zone.options, function (o) {
          return o.value === at.timezone;
        })) {
          zone.insertBefore(el("option", { value: at.timezone, text: at.timezone }), zone.firstChild);
        }
        zone.value = at.timezone;
      } else {
        var index = (book.places || []).findIndex(function (p) {
          return p.latitude === at.latitude && p.longitude === at.longitude &&
            p.timezone === at.timezone;
        });
        where.value = index >= 0 ? "city" + index : "custom";
      }
      var showCustom = where.value === "custom";
      customRows.forEach(function (r) { r.hidden = !showCustom; });
      where.disabled = useLocation.disabled = calendar.mode === "none";
    });
    return section;
  }

  var WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Shabbat"];
  var MONTHS = ["Nisan", "Iyar", "Sivan", "Tammuz", "Av", "Elul", "Tishrei", "Heshvan",
                "Kislev", "Tevet", "Shevat", "Adar", "Adar II"];

  // A value as it stands on the day that is ending, and whether the next one has begun to.
  function plain(value) {
    return value !== null && typeof value === "object" && "twilight" in value ? value.twilight[0] : value;
  }

  function get(settings, fs, name) {
    return settings[fs] ? plain(settings[fs][name]) : undefined;
  }

  // What the book has worked out the day to be, in words.
  function describeDay(settings) {
    if (!hasCalendar || calendar.mode === "none") return "";
    if (dateSetAside) {
      return "Your settings say it is another day than the date, so the date is set aside, " +
        "and the book follows your settings. Clear them in Advanced to follow the date again.";
    }
    var at = place();
    if (!at) {
      return "Choose a place, and the book works out the day — its date by the Hebrew " +
        "calendar, its holidays, the service — and follows it.";
    }
    var parts = [];
    var weekday = get(settings, "opensiddur:day-of-week", "hebrew-day");
    var year = get(settings, "opensiddur:hebrew-date", "year");
    var month = get(settings, "opensiddur:hebrew-date", "month");
    var day = get(settings, "opensiddur:hebrew-date", "day");
    if (typeof weekday === "number") parts.push(WEEKDAYS[weekday - 1]);
    if (typeof day === "number" && typeof month === "number") {
      var leap = get(settings, "opensiddur:hebrew-date", "leap-year");
      var name = month === 12 && leap ? "Adar I" : MONTHS[month - 1];
      parts.push(day + " " + name + " " + year);
    }
    var text = parts.join(", ");
    if (get(settings, "opensiddur:day-of-week", "bayn-hashmashot")) {
      text += ", between sunset and nightfall";
    }
    var service = ["shaharit", "minha", "maariv"].filter(function (s) {
      return get(settings, "opensiddur:service-time", s) === true;
    });
    var services = { shaharit: "Shaharit", minha: "Minha", maariv: "Ma'ariv" };
    if (service.length) text += " · " + services[service[0]];
    text += " · " + (calendar.place ? calendar.place.name : "the place given");
    return (calendar.mode === "chosen" ? "Chosen day: " : "") + text;
  }

  // ── Dialogs ────────────────────────────────────────────────────────────

  // A header with the title and ×, a body that scrolls, and a footer that does not, so its
  // buttons are always in reach however long the body.
  function dialogFrame(id, title, closeLabel) {
    var dialog = el("dialog", { id: id, class: "os-dialog", "aria-labelledby": id + "-title" });
    var close = el("button", { type: "button", class: "os-x", "aria-label": closeLabel, text: "×" });
    close.addEventListener("click", function () { dialog.close(); });
    var body = el("div", { class: "os-dialog-body" });
    var footer = el("div", { class: "os-dialog-footer" });
    dialog.appendChild(el("div", { class: "os-dialog-header" }, [
      el("h2", { id: id + "-title", text: title }), close]));
    dialog.appendChild(body);
    dialog.appendChild(footer);
    // A click on the backdrop lands on the dialog element itself -- but so does the end of a
    // drag that began inside it, and a press that began inside it is not a click outside.
    var pressedOutside = false;
    dialog.addEventListener("pointerdown", function (event) {
      pressedOutside = event.target === dialog && outside(dialog, event);
    });
    dialog.addEventListener("click", function (event) {
      if (pressedOutside && event.target === dialog && outside(dialog, event)) dialog.close();
      pressedOutside = false;
    });
    // Escape closes the dialog by itself; what closing means is the close event's to say.
    return { dialog: dialog, body: body, footer: footer };
  }

  function outside(dialog, event) {
    var box = dialog.getBoundingClientRect();
    return event.clientX < box.left || event.clientX > box.right ||
           event.clientY < box.top || event.clientY > box.bottom;
  }

  function button(text, className, onClick) {
    var b = el("button", { type: "button", class: className || "", text: text });
    b.addEventListener("click", onClick);
    return b;
  }

  var settingsFrame = null;

  function settingsDialog() {
    var snapshot = "{}";
    var calendarSnapshot = "{}";
    var displaySnapshot = "{}";
    var done = false;
    var frame = dialogFrame("os-settings", "Settings", "Cancel");
    settingsFrame = frame;

    // However the dialog closes -- ×, Cancel, Escape, a click outside -- the settings go back
    // to what they were when it opened, unless the reader said Done.
    frame.dialog.addEventListener("close", function () {
      // Restored or kept, the settings are applied with the anchor still held.
      var release = function () { heldAnchor = null; };
      window.setTimeout(release, 0);
      if (done) {
        saveSettings(reader);
        saveCalendar();
        saveDisplay();
      } else {
        reader = JSON.parse(snapshot);
        calendar = JSON.parse(calendarSnapshot);
        display = JSON.parse(displaySnapshot);
        changed();
      }
    });

    var body = frame.body;
    body.appendChild(el("p", { class: "os-note", text:
      "Choose what applies, and the book shows what you say. A passage that depends on " +
      "something not set is shown with the instruction for when to say it, as in the " +
      "printed book." }));

    if (book.columns) body.appendChild(columnsControl());
    if (hasCalendar) body.appendChild(dayControls());

    if (book.basic && book.basic.length) {
      var basic = el("div", { class: "os-basic" });
      book.basic.forEach(function (entry) {
        if (entry.type === "control") {
          basic.appendChild(compositeControl(entry));
        } else {
          var feature = features[entry.fs + "\u0000" + entry.name];
          if (feature) basic.appendChild(featureControl(feature, featureLabel(feature)));
        }
      });
      body.appendChild(basic);
    }

    var advanced = el("details", { class: "os-advanced" }, [
      el("summary", { text: "Advanced: set each feature" })]);
    var groups = {};
    book.features.forEach(function (feature) {
      (groups[feature.fs] = groups[feature.fs] || []).push(feature);
    });
    Object.keys(groups).sort().forEach(function (fs) {
      var fieldset = el("fieldset", {}, [el("legend", { text: words(fs) })]);
      groups[fs].forEach(function (feature) {
        fieldset.appendChild(featureControl(feature, featureLabel(feature)));
      });
      advanced.appendChild(fieldset);
    });
    body.appendChild(advanced);

    if (hasCalendar) {
      var calendarNote = el("p", { class: "os-note" });
      body.appendChild(calendarNote);
      refreshers.push(function () {
        var count = passages(book.calendarScopes);
        calendarNote.textContent = following() ? "" : calendar.mode === "none"
          ? count + " depend on the day, the time or the place. With no particular day, set " +
            "them here by hand; or choose Now, and a place, for the book to work them out."
          : count + " depend on the day, the time or the place. Choose a place, and the book " +
            "works them out.";
        calendarNote.hidden = !calendarNote.textContent;
      });
    }

    frame.footer.appendChild(button("Clear all", "os-clear", function () {
      reader = {};
      calendar = { mode: startingMode(), place: null };
      display = startingDisplay();
      changed();
    }));
    frame.footer.appendChild(el("span", { class: "os-spacer" }));
    frame.footer.appendChild(button("Cancel", "", function () { frame.dialog.close(); }));
    frame.footer.appendChild(button("Done", "os-primary", function () {
      done = true;
      frame.dialog.close();
    }));

    frame.open = function () {
      snapshot = JSON.stringify(reader);
      calendarSnapshot = JSON.stringify(calendar);
      displaySnapshot = JSON.stringify(display);
      done = false;
      resetDayControls();
      heldAnchor = anchor();
      refreshers.forEach(function (refresh) { refresh(); });
      frame.dialog.showModal();
    };
    return frame;
  }

  function contentsDialog() {
    var frame = dialogFrame("os-contents", "Contents", "Close");
    var list = el("ol", { class: "os-contents" });
    var headings = document.querySelectorAll(".os-book :is(h1, h2, h3, h4)");
    var shown = OSCond.sectionsShown(book, resolveAll().states);
    Array.prototype.forEach.call(headings, function (heading, index) {
      if (Number(heading.tagName.slice(1)) > book.contentsDepth) return;
      // A translated heading repeats its row's, unless the translation is shown alone.
      if (heading.closest(".col-parallel") && shownColumns() !== "parallel") return;
      if (!heading.getClientRects().length) return;  // in a passage the settings hide
      // A section none of whose text will show, though its heading does.
      if (heading.dataset.section !== undefined && !shown[Number(heading.dataset.section)]) return;
      if (!heading.id) heading.id = "os-heading-" + index;
      var link = el("a", { href: "#" + heading.id, text: heading.textContent.trim() });
      link.addEventListener("click", function () { frame.dialog.close(); });
      list.appendChild(el("li", { class: "os-contents-" + heading.tagName.toLowerCase() }, [link]));
    });
    frame.body.appendChild(list);
    frame.footer.appendChild(el("span", { class: "os-spacer" }));
    frame.footer.appendChild(button("Close", "os-primary", function () { frame.dialog.close(); }));
    return frame;
  }

  // ── Start ──────────────────────────────────────────────────────────────

  var toolbar = document.querySelector(".os-toolbar");
  var status = document.getElementById("os-status");
  if (hasCalendar && status) {
    status.setAttribute("aria-haspopup", "dialog");
    status.title = "The day and the place: open Settings to change them";
    statusListeners.push(function (settings) {
      var text = describeDay(settings);
      status.hidden = !text;
      say(status, dateSetAside ? "Following your settings, not the date"
                               : following() ? text : "Set the place");
    });
  }

  apply();

  var settings = settingsDialog();
  document.body.appendChild(settings.dialog);
  toolbar.hidden = false;
  document.getElementById("os-open-settings").addEventListener("click", settings.open);
  if (status) status.addEventListener("click", settings.open);

  if (hasCalendar) {
    window.setInterval(tick, 20000);
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) tick();
    });
    window.addEventListener("focus", tick);
    refreshLocation();
  }

  // A place from the device's location follows the device, if the reader has allowed that
  // already: the book never asks on opening. Otherwise it is the last one known.
  function refreshLocation() {
    if (!calendar.place || calendar.place.source !== "geolocation") return;
    if (!navigator.permissions || !navigator.permissions.query) return;
    navigator.permissions.query({ name: "geolocation" }).then(function (permission) {
      if (permission.state !== "granted") return;
      locate(function (location) {
        if (settings.dialog.open) return;  // the reader is changing the settings
        setPlace(location, "Your location", "geolocation");
        saveSettings(reader);
        saveCalendar();
        changed();
      }, function () { /* the last one known stands */ });
    }, function () { /* the last one known stands */ });
  }
  // Built afresh each time: which headings are shown depends on the settings.
  document.getElementById("os-open-contents").addEventListener("click", function () {
    var old = document.getElementById("os-contents");
    if (old) old.remove();
    var contents = contentsDialog();
    document.body.appendChild(contents.dialog);
    contents.dialog.showModal();
  });

  // ── Links within the book ──────────────────────────────────────────

  // The toolbar stays at the top of the window: a passage linked to goes below it.
  function padForToolbar() {
    document.documentElement.style.scrollPaddingTop = toolbar.offsetHeight + "px";
  }
  padForToolbar();
  window.addEventListener("resize", padForToolbar);

  // Where a link goes. A page reference's destination can occur more than once, and the
  // settings can hide the first: go to the first they show.
  function destination(hash) {
    var id = hash.slice(1);
    try { id = decodeURIComponent(id); } catch (e) { /* use it as it is */ }
    if (!id) return null;
    var copies = document.querySelectorAll('[data-page-label="' + CSS.escape(id) + '"]');
    for (var i = 0; i < copies.length; i++) {
      if (copies[i].getClientRects().length) return copies[i];
    }
    return document.getElementById(id);
  }

  // Rows off screen are not laid out (content-visibility: auto) until the browser passes them,
  // and their real heights move a passage after the browser has gone to it. Go to it again
  // whenever it moves, until it has stayed put for a few frames, or until the reader scrolls.
  var settling = 0;
  function settleOn(hash) {
    var target = destination(hash);
    if (!target) return;
    var run = ++settling, frames = 0, still = 0;
    target.scrollIntoView();
    var last = target.getBoundingClientRect().top;
    (function check() {
      if (run !== settling) return;
      var top = target.getBoundingClientRect().top;
      if (Math.abs(top - last) > 1) {
        target.scrollIntoView();
        last = target.getBoundingClientRect().top;
        still = 0;
      } else still++;
      if (still < 3 && ++frames < 60) requestAnimationFrame(check);
    })();
  }
  ["wheel", "touchstart", "pointerdown", "keydown"].forEach(function (type) {
    window.addEventListener(type, function () { settling++; keeping++; }, { passive: true });
  });
  document.addEventListener("click", function (event) {
    if (event.defaultPrevented || event.button || event.ctrlKey || event.metaKey
        || event.shiftKey || event.altKey) return;
    var link = event.target.closest && event.target.closest('a[href^="#"]');
    // After the browser's own jump, which goes nowhere if the settings hide the first copy.
    if (link) requestAnimationFrame(function () { settleOn(link.getAttribute("href")); });
  });
  window.addEventListener("hashchange", function () { settleOn(location.hash); });

  // Passages shown or hidden above may have moved a linked one: go to it again.
  if (location.hash) settleOn(location.hash);
})();
