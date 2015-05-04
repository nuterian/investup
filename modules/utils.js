var https       		= require('https');
var profileFeatures     = require('./profileFeatures').profileFeatures;

var API_KEY = "26bb2c820b0842a99cba19563c196506";

function getOrganizationData(permalink, callback) {
	var url = 'https://api.crunchbase.com/v/3/organizations/' + permalink + '?user_key=' + API_KEY;
	var statusCode = -1;
	https.get(url, function(res) {
		statusCode = res.statusCode;
	    res.setEncoding('utf8');
	    var data = '';

	    res.on('data', function (chunk) {
	        data += chunk;
	    });

	    res.on('end', function(){
	        callback(data, statusCode);
	    });
	}).on('error', function(e) {
		callback('', statusCode);
	});
}

function getKeywordMatchScore(a, keys) {
    var score = 0;

    a = a.toLowerCase();
    a = a.replace(/\W+/g, ' '); //Convert all non-word characters to spaces.
    _a = a.split(' ');

    keys.forEach(function(k, i) {
        _a.forEach(function(b, j){
            if( b == k ) {
                score += 10;
                if(i == j) {
                    score += 3;
                }
                else {
                    score -= 1;
                }
            }
            else if(b.indexOf(k) > -1) {
                score += 3;
                if(i == j) {
                    score += 2;
                }
            }
            else {
                score -= 1;//Math.abs(b.length - k.length);
            }
        });
    });

    var diff = Math.abs(_a.length - keys.length);
    score -= diff;

    return score;
}

function getOrganizationProfileFromData(data) {
	if(!data || data === '') {
		return null;
	}

	var ret = {};
	for(var feature in profileFeatures) {
		ret[feature] = profileFeatures[feature](data.data);
	}

	return ret;
}

module.exports = {
	getOrganizationData: getOrganizationData,
	getKeywordMatchScore: getKeywordMatchScore,
	getOrganizationProfileFromData: getOrganizationProfileFromData
}