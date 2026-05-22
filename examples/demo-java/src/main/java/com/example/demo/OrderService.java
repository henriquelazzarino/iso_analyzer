package com.example.demo;

import java.util.ArrayList;
import java.util.List;

public class OrderService {

    private final PriceCalculator calculator;
    private final Logger logger;

    public OrderService(PriceCalculator calculator, Logger logger) {
        this.calculator = calculator;
        this.logger = logger;
    }

    public double total(List<Order> orders) {
        double total = 0.0;
        for (Order o : orders) {
            if (o == null) {
                continue;
            } else if (o.getQuantity() <= 0) {
                logger.warn("invalid quantity");
            } else if (o.getQuantity() > 1000) {
                logger.warn("huge quantity");
            } else {
                total += calculator.compute(o);
            }
        }
        return total;
    }

    public List<Order> nonEmpty(List<Order> orders) {
        List<Order> result = new ArrayList<>();
        for (Order o : orders) {
            if (o != null) {
                result.add(o);
            }
        }
        return result;
    }
}
