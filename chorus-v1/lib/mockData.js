function getDataset(query) {
  const q = query.toLowerCase();

  if (q.includes("hotel") || q.includes("stay") || q.includes("room")) {
    return [
      {
        id: "hotel-1",
        name: "Hotel Indigo Manchester Centre",
        category: "hotel",
        city: "Manchester",
        price: 118,
        rating: 8.8,
        distanceKm: 0.6,
        official: true,
        refundable: true,
        notes: ["Central", "Good review balance"]
      },
      {
        id: "hotel-2",
        name: "Travelodge Manchester Piccadilly",
        category: "hotel",
        city: "Manchester",
        price: 94,
        rating: 7.5,
        distanceKm: 1.3,
        official: true,
        refundable: false,
        notes: ["Cheap", "Basic room"]
      },
      {
        id: "hotel-3",
        name: "Motel One Manchester-St. Peter's Square",
        category: "hotel",
        city: "Manchester",
        price: 121,
        rating: 8.6,
        distanceKm: 0.4,
        official: true,
        refundable: true,
        notes: ["Very central", "Slightly above some budgets"]
      },
      {
        id: "hotel-4",
        name: "CitySuites II Aparthotel",
        category: "hotel",
        city: "Manchester",
        price: 139,
        rating: 9.1,
        distanceKm: 0.9,
        official: true,
        refundable: true,
        notes: ["Higher quality", "Often pricier"]
      }
    ];
  }

  if (q.includes("train") || q.includes("trip") || q.includes("travel") || q.includes("ticket")) {
    return [
      {
        id: "trip-1",
        name: "Direct train + standard hotel package",
        category: "trip",
        price: 219,
        rating: 8.4,
        distanceKm: 0.8,
        official: true,
        refundable: true,
        notes: ["Balanced total cost", "Direct travel"]
      },
      {
        id: "trip-2",
        name: "Cheapest split-ticket route + budget stay",
        category: "trip",
        price: 171,
        rating: 7.1,
        distanceKm: 2.3,
        official: false,
        refundable: false,
        notes: ["Lower price", "Higher hassle"]
      },
      {
        id: "trip-3",
        name: "Flexible rail fare + central hotel",
        category: "trip",
        price: 248,
        rating: 8.9,
        distanceKm: 0.5,
        official: true,
        refundable: true,
        notes: ["Safer option", "More expensive"]
      }
    ];
  }

  return [
    {
      id: "prod-1",
      name: "Samsung 65-inch 4K TV",
      category: "product",
      price: 699,
      rating: 8.3,
      distanceKm: 0,
      official: true,
      refundable: true,
      notes: ["Strong mainstream option", "Gaming features decent"]
    },
    {
      id: "prod-2",
      name: "TCL 65-inch QLED TV",
      category: "product",
      price: 579,
      rating: 8.1,
      distanceKm: 0,
      official: true,
      refundable: true,
      notes: ["Better value", "Lower brand confidence for some buyers"]
    },
    {
      id: "prod-3",
      name: "Hisense 65-inch Mini-LED TV",
      category: "product",
      price: 649,
      rating: 8.5,
      distanceKm: 0,
      official: true,
      refundable: true,
      notes: ["Good picture value", "Stock can vary"]
    },
    {
      id: "prod-4",
      name: "Unknown Marketplace Seller TV Deal",
      category: "product",
      price: 499,
      rating: 6.2,
      distanceKm: 0,
      official: false,
      refundable: false,
      notes: ["Very cheap", "Seller risk high"]
    }
  ];
}

module.exports = { getDataset };
