Feature: Collecting weather readings for a city
  As a consumer of the weather aggregator
  I want to fetch and re-read current conditions for a city
  So that I can see both the latest weather and how it was polled over time

  Background:
    Given the weather service knows about "Bengaluru" at 12.97194, 77.59369
    And no readings are stored

  Scenario: Fetching a city stores a reading and returns it
    When I fetch the weather for "Bengaluru"
    Then the response status is 201
    And the response is for the city "Bengaluru"
    And 1 reading is stored for "Bengaluru"

  Scenario: Repeated fetches build a history rather than overwriting
    When I fetch the weather for "Bengaluru"
    And I fetch the weather for "Bengaluru"
    And I fetch the weather for "Bengaluru"
    Then 3 readings are stored for "Bengaluru"
    And all stored readings share the same observation time
    And the readings are ordered most recent first

  Scenario: The latest reading is available on its own
    Given I have fetched the weather for "Bengaluru" 2 times
    When I ask for the latest reading for "Bengaluru"
    Then the response status is 200
    And the response is for the city "Bengaluru"

  Scenario: A city that cannot be resolved is reported as not found
    When I fetch the weather for "Atlantis"
    Then the response status is 404
    And no readings are stored for "Atlantis"

  Scenario: Asking for a city with no readings is not a silent empty answer
    When I ask for the readings for "Bengaluru"
    Then the response status is 404

  Scenario: An upstream failure is reported as a bad gateway, not a server error
    Given the upstream weather service is failing with 503
    When I fetch the weather for "Bengaluru"
    Then the response status is 502
    And no readings are stored for "Bengaluru"

  Scenario: City names are matched regardless of case
    Given I have fetched the weather for "Bengaluru" 1 times
    When I ask for the readings for "BENGALURU"
    Then the response status is 200
    And 1 reading is stored for "bengaluru"
