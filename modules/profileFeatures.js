var moment = require('moment');

var profileFeatures = {

	name: function(d) {
		return d.properties.name;
	},

	description: function(d) {
		return d.properties.short_description;
	},

	total_funding: function(d) {
		return d.properties.total_funding_usd;
	},

	homepage_url: function(d) {
		return d.properties.homepage_url;
	},

	location: function(d) {
		var address = null;
		if(d.relationships.headquarters) {
			address = d.relationships.headquarters.item.properties;
		}
		else if(d.relationships.offices) {
			address = d.relationships.offices.items[d.relationships.offices.items.length - 1].properties;
		}

		if(address) {
			return {
				c: address.city,
				r: address.region,
				y: address.country
			};
		}
		return null;
	},

	num_employees : function(d) {
		var min = d.properties.num_employees_min || 0;
		var max = d.properties.num_employees_max || 0;
		if(min === max) {
			if(min === 0) return null;
			return min;
		}
		return min + '-' + max;
	},

	founded_on: function(d) {
		return d.properties.founded_on;
	},

	age: function(d){
		if(!d.properties.founded_on) return null;
		var from = moment(d.properties.founded_on);
		var to = d.properties.closed_on ? moment(d.properties.closed_on) : moment();
		if(d.relationships.acquired_by){
			var acquiredItems = d.relationships.acquired_by.items;
			var mostRecentAcquiredDate = from;
			acquiredItems.forEach(function(a) {
				if(a.type.announced_on) {
					var acquiredDate = moment(a.type.announced_on);
					if(acquiredDate.isAfter(mostRecentAcquiredDate)){
						mostRecentAcquiredDate = acquiredDate;
					}
				}
			});

			if(mostRecentAcquiredDate.isAfter(from)) {
				to = mostRecentAcquiredDate;
			}
		}
		return moment(to).diff(from, 'months');
	},

	competitors: function(d) {
		var competitors = d.relationships.competitors;
		if(competitors) {
			var ret = [];
			competitors = competitors.items;
			competitors.forEach(function(c) {
				ret.push(c.properties.permalink);
			});
			return ret;
		}
		return [];	
	},

	num_competitors: function(d){
		if(d.relationships.competitors) {
			return d.relationships.competitors.items.length;
		}
		return 0;
	},

	num_offices: function(d){
		if(d.relationships.offices) {
			return d.relationships.offices.items.length;
		}
		return 0;
	},

	num_products: function(d){
		if(d.relationships.products) {
			return d.relationships.products.items.length;
		}
		return 0;
	},

	total_funding_investments: function(d) {
		if(d.relationships.investments) {
			var items = d.relationships.investments.items;
			var total = 0;
			items.forEach(function(i){
				if(i.relationships && i.relationships.funding_round) {
					total += i.relationships.funding_round.properties.money_raised_usd || 0;
				}
			});
			return total;
		}
		return 0;		
	},

	num_investments: function(d){
		return d.properties.number_of_investments || 0;
	},

	num_acquisitions: function(d){
		if(d.relationships.acquisitions) {
			return d.relationships.acquisitions.items.length;
		}
		return 0;
	},

	num_investors_orgs: function(d) {
		if(d.relationships.investors) {
			var investors = d.relationships.investors.items;
			var count = 0;
			investors.forEach(function(i){
				if(i.type === "Organization") {
					count++;
				}
			});
			return count;
		}	
		return 0;	
	},

	num_investors_persons: function(d) {
		if(d.relationships.investors) {
			var investors = d.relationships.investors.items;
			var count = 0;
			investors.forEach(function(i){
				if(i.type === "Person") {
					count++;
				}
			});
			return count;
		}	
		return 0;
	},

	funding_rounds: function(d) {
		var rounds = d.relationships.funding_rounds;
		if(rounds) {
			var ret = [];
			rounds = rounds.items;
			rounds.forEach(function(r) {
				if(r.properties.money_raised_usd !== null && r.properties.announced_on !== null) {
					ret.push({d:r.properties.announced_on,a:r.properties.money_raised_usd});
				}
			});
			return ret;
		}
		return [];			
	},

	num_funding_rounds: function(d){
		if(d.relationships.funding_rounds) {
			return d.relationships.funding_rounds.items.length;
		}
		return 0;
	},

	funding_per_round: function(d){
		if(d.relationships.funding_rounds) {
			var rounds = d.relationships.funding_rounds.items;
			var total = 0, count = 0;
			rounds.forEach(function(r){
				if(r.properties.money_raised_usd) {
					total += r.properties.money_raised_usd || 0;
					count++;
				}
			});

			return count === 0 ? 0 : (total/count).toFixed(3);
		}
		return 0;
	}
};

module.exports = {
	profileFeatures: profileFeatures,
	trainingFeatures: [
		'age',
		'num_employees',
		'num_competitors',
		'num_offices',
		'num_products',
		'num_investments',
		'num_acquisitions',
		'num_investors_orgs',
		'num_investors_persons',
		'funding_rounds',
		'funding_per_round'
	]
}