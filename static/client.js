(function () {
  if (getSessionState() == "running") {
    launch_db_run();
  }
})();

var slider = document.getElementById("ttl-slider");
// Update the current slider value (each time you drag the slider handle)
slider.oninput = function () {
  console.log("value: " + this.value);
  var output = document.getElementById("demo");
  output.innerHTML = "TTL is set to " + this.value + " milliseconds";
  setSessionStopped();
};

var dataslider = document.getElementById("data-slider");
// Update the current slider value (each time you drag the slider handle)
dataslider.oninput = function () {
  console.log("value: " + this.value);
  var output = document.getElementById("data-demo");
  output.innerHTML = "" + this.value + " different queries";
  setSessionStopped();
};

var totalslider = document.getElementById("total-slider");
// Update the current slider value (each time you drag the slider handle)
totalslider.oninput = function () {
  console.log("value: " + this.value);
  var output = document.getElementById("data-total");
  output.innerHTML = "" + this.value + " total calls";
  setSessionStopped();
};

var complexity = document.getElementById("complexity");
// Update the current slider value (each time you drag the slider handle)
complexity.oninput = function () {
  console.log("value: " + this.value);
};

window.onload = function () {
  window.redis_times = 0;
  window.db_times = 0;
  window.redis_qps = 0;
  window.db_qps = 0;

  if (window.clientID == "") {
    window.clientID = "#" + Math.floor(Math.random() * 16777215).toString(16);
  }
};

function get_BaseURL() {
  return window.location.origin + "/";
}

function launch_db_run() {
  window.lastquery = 0;
  const request = new XMLHttpRequest();
  setSessionRunning();
  const base_url = get_BaseURL() + "start_db_run";
  request.open(
    "GET",
    base_url +
      "?ttl=" +
      document.getElementById("ttl-slider").value +
      "&possibilites=" +
      document.getElementById("data-slider").value +
      "&complexity=" +
      document.getElementById("complexity").value +
      "&db=" +
      document.getElementById("db").value +
      "&runs=" +
      document.getElementById("total-slider").value
  );
  request.send();
}

function make_table(data, titles, fields) {
  response = "<tr>";
  for (ii = 0; ii < titles.length; ii++) {
    response += "<th>" + titles[ii] + "</th>";
  }
  response += "</tr>";
  for (ii = 0; ii < data.length; ii++) {
    var line = JSON.parse(data[ii]);
    response += "<tr>";
    for (jj = 0; jj < fields.length; jj++) {
      response += "<td>" + line[fields[jj]] + "</td>";
    }
    response += "</tr>";
  }
  return response;
}

function load_time_values() {
  const request = new XMLHttpRequest();
  const base_url = get_BaseURL() + "get/latest_time" + "?id=" + window.clientID;
  request.open("GET", base_url);
  request.send();
  request.onreadystatechange = function () {
    let data = request.response;
    if (data != "") {
      console.log(data);
      rTime = data.split("|")[0];
      mTime = data.split("|")[1];
      window.redis_times = Math.round(rTime);
      window.db_times = Math.round(mTime);
      window.redis_qps = 1000000 / Math.round(rTime);
      window.db_qps = 1000000 / Math.round(mTime);

      if (!isNaN(window.db_qps) && !isNaN(window.redis_qps)) {
        var elem1 = document.getElementById("cache-query-bar");
        elem1.setAttribute("aria-valuenow", Math.round(redis_qps) / 40);
        elem1.setAttribute("style", "width:" + Number(redis_qps / 40) + "%");
        document.getElementById("redis_qps").innerHTML = Math.round(redis_qps);
        var elem2 = document.getElementById("db-query-bar");
        elem2.setAttribute("aria-valuenow", Math.round(db_qps) / 40);
        elem2.setAttribute("style", "width:" + Number(db_qps / 40) + "%");
        document.getElementById("db_qps").innerHTML = Math.round(db_qps);
      }
    }
  };
}

function get_table_data(div, urlPath, titles, fields) {
  const request = new XMLHttpRequest();
  const base_url = get_BaseURL() + "get/" + urlPath + "?id=" + window.clientID;
  request.open("GET", base_url);
  request.send();
  request.onreadystatechange = function () {
    let data = request.response;
    if (data != "") {
      var obj = JSON.parse(data);
      outDiv = document.getElementById(div);
      outDiv.innerHTML = make_table(obj, titles, fields);
    }
  };
}

function update_hit_miss() {
  const request = new XMLHttpRequest();
  request.open(
    "GET",
    get_BaseURL() + "get/db_cache" + "?id=" + window.clientID
  );
  request.send();
  request.onreadystatechange = function () {
    if (request.responseText != "") {
      var hits = parseInt(request.responseText.split("|")[0]);
      var misses = parseInt(request.responseText.split("|")[1]);
      var total = hits + misses;
      var ratio = hits / total;
      var elem2 = document.getElementById("progress-status");
      var progress =
        (hits + misses) /
        parseInt(document.getElementById("total-slider").value);
      elem2.setAttribute("aria-valuenow", progress * 100);
      elem2.setAttribute("style", "width:" + progress * 100 + "%");

      var elem3 = document.getElementById("state");
      console.log("message");
      elem3.innerHTML = Math.round(progress * 100) + "%";

      if (progress == 1) {
        setSessionStopped();
      }

      console.log("Hits: " + hits + " , Total:" + total);
      document.getElementById("ratio").innerHTML = ratio.toFixed(3);
      elem = document.getElementById("cache-hit-bar");
      elem.setAttribute("aria-valuenow", ratio.toFixed(3) * 100);
      elem.setAttribute("style", "width:" + ratio.toFixed(3) * 100 + "%");
      console.log("graphdata: " + request.responseText);
      drawPlot(hits, misses);
    }
  };
}

function setSessionStopped() {
  sessionStorage.setItem("state", "stopped");
  var elem2 = document.getElementById("progress-status");
}

function setSessionRunning() {
  sessionStorage.setItem("state", "running");
  displaySessionState("running");
}

function displaySessionState(state) {}

function getSessionState() {
  return sessionStorage.getItem("state");
}
function drawPlot(hits, misses) {
  try {
    y1 = hits;
    y2 = misses;
  } catch (error) {
    return;
  }

  var trace1 = {
    x: ["Hits"],
    y: [y1],
    text: window.redis_times + "μs per call<br><br>" + hits + " cache hits",
    textposition: "auto",
    hoverinfo: "none",
    type: "bar",
    name: "bb",
  };
  var trace2 = {
    x: ["Misses"],
    y: [y2],
    text: window.db_times + "μs per call<br><br>" + misses + " cache misses",
    textposition: "auto",
    hoverinfo: "none",
    type: "bar",
    name: "xx",
  };

  var data = [trace1, trace2];

  var layout = {
    title: "",
    yaxis: {
      title: {
        text: "Number of Queries",
      },
    },
    showlegend: false,
  };

  Plotly.newPlot("graph", data, layout, { displayModeBar: false });
}

function update_ux() {
  console.log(getSessionState());
  if (getSessionState() == "running") {
    console.log("runnign and refreshing");
    load_time_values();
    get_table_data(
      "log_tbl",
      "log/DBCACHE",
      ["SQL", "Hit / Miss"],
      ["sql_txt", "hm"]
    );
    update_hit_miss();
  }
}

window.setInterval(update_ux, 1000);

