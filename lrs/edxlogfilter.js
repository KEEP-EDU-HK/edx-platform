/** Import libraries **/
/**
* Installation:
* npm install --save async
* npm install --save fs
* npm install --save lazy
**/

var fs = require('fs');
var lazy = require('lazy');
var async = require('async');

var jsonfile = process.argv[2];
var jsonbackupfile = process.argv[3];
var starttime = process.argv[4];
var endtime = process.argv[5];
var output = process.argv[6];

/**
 * This function is used to extract valid logs within the given period
 **/
function parseData(line) {
    try {
        var s = JSON.parse(line);
        if (s["username"] != '' && s["time"] >= starttime & s["time"] < endtime) {
            return JSON.stringify(s);
        } else {
            return false;
        }
    }
    catch(err) {
        return false;
    } 
}
console.log("------------------------------------------------------------------");
console.log("Starting edxlogfilter from " + starttime + " to " + endtime);
async.waterfall([
        // 1st - check if log records exist in log file from last log rotatation
        function(callback) {
            var backup = false;
            new lazy(fs.createReadStream(jsonfile))
                .lines
                .map(String)
                .take(1)
                .map(function(line) {
                    var s = JSON.parse(line);
                    console.log("Tracking log start @" + s["time"]);
                    if (s["time"] > starttime) {
                        backup = true;
                        console.log("Log may exist in backup file");
                    }
                })
                .on('pipe', function() {
                    callback(null, backup);
                });
        },
        // 2nd - if log records exist in last log rotatation, i.e. backup file
        function(backup, callback) {
            var logs = [];
            if (backup) {
                console.log("Reading backup logs...");
                new lazy(fs.createReadStream(jsonbackupfile))
                    .lines
                    .map(String)
                    .map(parseData)
                    .join(function(lines) {
                        for (var i = 0; i < lines.length; i++) {
                            if (lines[i] != false) {
                                logs.push(lines[i]);
                            }
                        }
                    })
                    .on('pipe', function() {
                        console.log("# of logs in backup:\t" + logs.length);
                        callback(null, logs);
                    });
            } else {
                console.log("Skipping backup logs...");
                callback(null, logs);
            }

        },
        // 3rd- get all the remaining log within the given period
        function(logs, callback) {
            if (typeof logs !== 'undefined' && logs.length > 0) {
                var lastlog = JSON.parse(logs.slice(-1).pop());
                starttime = lastlog["time"];
                console.log("Udapting start time to: " + starttime);
            }
            new lazy(fs.createReadStream(jsonfile))
                .lines
                .map(String)
                .map(parseData)
                .join(function(lines) {
                    for (var i = 0; i < lines.length; i++) {
                        if (lines[i] != false) {
                            logs.push(lines[i]);
                        }
                    }
                })
                .on('pipe', function() {
                    console.log("# of logs in total:\t" + logs.length);
                    callback(null, logs);
                });
        }
    ],
    // 4th - write log to files
    function(err, results) {
        var logs = [];
        for (var i = 0; i < results.length; i++) {
            logs = logs.concat(results[i]);
        }
        // var path = prefix + output;
        fs.writeFile(output, logs.join("\n"), function(err) {
            if (err) throw err;
        })
    }
);

